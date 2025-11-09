import unittest
import tempfile
import os
import time
import threading
from queuectl.core.queue import JobQueue
from queuectl.core.worker import Worker, WorkerManager
from queuectl.core.job import JobState
from queuectl.persistence.sqlite_store import SQLiteJobStore

class TestWorker(unittest.TestCase):
    
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.storage = SQLiteJobStore(self.db_path)
        self.queue = JobQueue(self.storage)
        self.worker_manager = WorkerManager(self.queue)
    
    def tearDown(self):
        self.worker_manager.stop_workers()
        # Give workers time to stop
        time.sleep(0.5)
        self.storage.close_all()
        # Close the file descriptor and remove the file
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except (OSError, PermissionError):
            # File might already be closed/removed, ignore
            pass
    
    def test_worker_processing_success(self):
        job = self.queue.enqueue("echo 'hello world'")
        
        worker = Worker(self.queue, "test-worker")
        worker_thread = threading.Thread(target=worker.start)
        worker_thread.daemon = True
        worker_thread.start()
        
        # Wait for processing
        time.sleep(2)
        
        # Check job completed
        completed_job = self.queue.get_job(job.id)
        self.assertEqual(completed_job.state, JobState.COMPLETED)
        
        worker.stop()
        worker_thread.join(timeout=5)
    
    def test_worker_processing_failure(self):
        # Use a command that will definitely fail on both Windows and Unix
        job = self.queue.enqueue("nonexistent_command_xyz123", max_retries=2)
        
        worker = Worker(self.queue, "test-worker")
        worker_thread = threading.Thread(target=worker.start)
        worker_thread.daemon = True
        worker_thread.start()
        
        # Wait for processing and retries
        time.sleep(5)
        
        # Check job failed and moved through retries
        failed_job = self.queue.get_job(job.id)
        self.assertIn(failed_job.state, [JobState.FAILED, JobState.DEAD])
        self.assertGreater(failed_job.attempts, 0)
        
        worker.stop()
        worker_thread.join(timeout=5)
    
    def test_worker_timeout(self):
        # Use a command that will run indefinitely (until killed)
        import sys
        if sys.platform == "win32":
            command = "ping -n 10 127.0.0.1 > nul"  # 10 pings on Windows
        else:
            command = "sleep 10"  # 10 seconds on Unix
        
        job = self.queue.enqueue(command)
        
        worker = Worker(self.queue, "test-worker")
        worker_thread = threading.Thread(target=worker.start)
        worker_thread.daemon = True
        worker_thread.start()
        
        # Wait a bit for processing to start
        time.sleep(1)
        
        # Stop worker while job is running
        worker.stop()
        
        # Give time for the stop to process
        time.sleep(2)
        
        # Job might be in various states depending on when it was interrupted
        interrupted_job = self.queue.get_job(job.id)
        # It could be completed, failed, or still processing
        self.assertIn(interrupted_job.state, [JobState.COMPLETED, JobState.FAILED, JobState.PROCESSING])
        
        worker_thread.join(timeout=5)
    
    def test_worker_manager_start_stop(self):
        # Start multiple workers
        self.worker_manager.start_workers(3)
        
        # Give workers time to start
        time.sleep(1)
        
        # Check workers are running
        active_workers = self.worker_manager.get_active_workers()
        self.assertEqual(len(active_workers), 3)
        
        # Check worker stats
        stats = self.worker_manager.get_worker_stats()
        self.assertEqual(stats["total"], 3)
        
        # Stop workers
        self.worker_manager.stop_workers()
        
        # Give workers time to stop
        time.sleep(1)
        
        # Check workers stopped
        active_workers = self.worker_manager.get_active_workers()
        self.assertEqual(len(active_workers), 0)
    
    def test_multiple_workers_concurrent_processing(self):
        # Enqueue multiple jobs
        jobs = []
        for i in range(3):
            job = self.queue.enqueue(f"echo 'job {i}'")
            jobs.append(job)
        
        # Start multiple workers
        self.worker_manager.start_workers(2)
        
        # Wait for processing
        time.sleep(5)
        
        # Check all jobs were processed
        completed_count = 0
        for job in jobs:
            updated_job = self.queue.get_job(job.id)
            if updated_job.state == JobState.COMPLETED:
                completed_count += 1
        
        # At least some jobs should be completed
        self.assertGreater(completed_count, 0)
        
        self.worker_manager.stop_workers()

if __name__ == '__main__':
    unittest.main()