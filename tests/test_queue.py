import unittest
import tempfile
import os
from queuectl.core.queue import JobQueue
from queuectl.core.job import Job, JobState
from queuectl.persistence.sqlite_store import SQLiteJobStore

class TestJobQueue(unittest.TestCase):
    
    def setUp(self):
       
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.storage = SQLiteJobStore(self.db_path)
        self.queue = JobQueue(self.storage)
    
    def tearDown(self):
        self.storage.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_enqueue_job(self):
        job = self.queue.enqueue("echo hello", "test-job", 3)
        
        self.assertEqual(job.command, "echo hello")
        self.assertEqual(job.id, "test-job")
        self.assertEqual(job.max_retries, 3)
        self.assertEqual(job.state, JobState.PENDING)
        
       
        retrieved = self.queue.get_job("test-job")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.command, "echo hello")
    
    def test_dequeue_job(self):
        job1 = self.queue.enqueue("echo first")
        job2 = self.queue.enqueue("echo second")
        
       
        dequeued = self.queue.dequeue()
        self.assertIsNotNone(dequeued)
        self.assertEqual(dequeued.id, job1.id)
        self.assertEqual(dequeued.state, JobState.PROCESSING)
        
        
        dequeued2 = self.queue.dequeue()
        self.assertEqual(dequeued2.id, job2.id)
        
       
        self.assertIsNone(self.queue.dequeue())
    
    def test_complete_job(self):
        job = self.queue.enqueue("echo hello")
        self.queue.complete_job(job.id)
        
        completed = self.queue.get_job(job.id)
        self.assertEqual(completed.state, JobState.COMPLETED)
    
    def test_fail_job_with_retry(self):
        job = self.queue.enqueue("echo hello", max_retries=2)
        
        # First failure
        self.queue.fail_job(job.id, "First error")
        failed = self.queue.get_job(job.id)
        self.assertEqual(failed.state, JobState.FAILED)
        self.assertEqual(failed.attempts, 1)
        self.assertIsNotNone(failed.next_retry_at)
        
        # Second failure should move to DLQ
        self.queue.fail_job(job.id, "Second error")
        dead = self.queue.get_job(job.id)
        self.assertEqual(dead.state, JobState.DEAD)
        self.assertEqual(dead.attempts, 2)
    
    def test_list_jobs(self):
        job1 = self.queue.enqueue("echo one")
        job2 = self.queue.enqueue("echo two")
        job3 = self.queue.enqueue("echo three")
        
        # Complete one job
        self.queue.complete_job(job1.id)
        
        # List all jobs
        all_jobs = self.queue.list_jobs()
        self.assertEqual(len(all_jobs), 3)
        
        # List pending jobs
        pending_jobs = self.queue.list_jobs(JobState.PENDING)
        self.assertEqual(len(pending_jobs), 2)
        
        # List completed jobs
        completed_jobs = self.queue.list_jobs(JobState.COMPLETED)
        self.assertEqual(len(completed_jobs), 1)
    
    def test_retry_dlq_job(self):
        job = self.queue.enqueue("echo hello", max_retries=1)
        
        # Fail job to move to DLQ
        self.queue.fail_job(job.id, "Error")
        self.queue.fail_job(job.id, "Error")  # Exhaust retries
        
        dead_job = self.queue.get_job(job.id)
        self.assertEqual(dead_job.state, JobState.DEAD)
        
        # Retry from DLQ
        success = self.queue.retry_dlq_job(job.id)
        self.assertTrue(success)
        
        retried_job = self.queue.get_job(job.id)
        self.assertEqual(retried_job.state, JobState.PENDING)
        self.assertEqual(retried_job.attempts, 0)
        self.assertIsNone(retried_job.last_error)
    
    def test_get_stats(self):
        self.queue.enqueue("echo one")
        self.queue.enqueue("echo two")
        job3 = self.queue.enqueue("echo three")
        
        # Complete one job
        self.queue.complete_job(job3.id)
        
        stats = self.queue.get_stats()
        self.assertEqual(stats["pending"], 2)
        self.assertEqual(stats["completed"], 1)
    
    def test_get_dlq_jobs(self):
        job1 = self.queue.enqueue("echo one", max_retries=1)
        job2 = self.queue.enqueue("echo two", max_retries=1)
        
        # Move both to DLQ
        self.queue.fail_job(job1.id, "Error")
        self.queue.fail_job(job1.id, "Error")
        
        self.queue.fail_job(job2.id, "Error") 
        self.queue.fail_job(job2.id, "Error")
        
        dlq_jobs = self.queue.get_dlq_jobs()
        self.assertEqual(len(dlq_jobs), 2)

if __name__ == '__main__':
    unittest.main()