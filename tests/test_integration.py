import unittest
import tempfile
import os
import time
import threading
from queuectl.core.queue import JobQueue
from queuectl.core.worker import WorkerManager
from queuectl.persistence.sqlite_store import SQLiteJobStore

class TestIntegration(unittest.TestCase):
    
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.storage = SQLiteJobStore(self.db_path)
        self.queue = JobQueue(self.storage)
        self.worker_manager = WorkerManager(self.queue)
    
    def tearDown(self):
        self.worker_manager.stop_workers()
        
        time.sleep(0.5)
        self.storage.close_all()
        
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except (OSError, PermissionError):
           
            pass
    
    def test_end_to_end_workflow(self):
        """Test complete workflow: enqueue -> process -> complete"""
        
     
        jobs = []
        for i in range(3):
            job = self.queue.enqueue(f"echo 'Processing item {i}'")
            jobs.append(job)
        
        self.worker_manager.start_workers(2)
        
        time.sleep(5)
        
        stats = self.queue.get_stats()
        self.assertEqual(stats["completed"], 3)
        
       
        self.worker_manager.stop_workers()
    
    def test_retry_mechanism_integration(self):
        """Test retry mechanism with failing commands"""
        
        
        job = self.queue.enqueue("nonexistent_command_xyz123", max_retries=2)
        
        self.worker_manager.start_workers(1)
        
        time.sleep(10)  
        
       
        final_job = self.queue.get_job(job.id)
        self.assertEqual(final_job.state.value, "dead")
        self.assertEqual(final_job.attempts, 2)
        
        self.worker_manager.stop_workers()
    
    def test_concurrent_worker_processing(self):
        """Test that multiple workers don't process the same job"""
        
       
        for i in range(5): 
            self.queue.enqueue(f"echo 'Job {i}'")
        
       
        self.worker_manager.start_workers(3)
      
        time.sleep(8)
        
        # Check no duplicate processing occurred
        all_jobs = self.queue.list_jobs()
        completed_count = sum(1 for job in all_jobs if job.state.value == "completed")
        
        # Should have exactly 5 completed jobs (no duplicates)
        self.assertEqual(completed_count, 5)
        
        self.worker_manager.stop_workers()

if __name__ == '__main__':
    unittest.main()