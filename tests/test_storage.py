import unittest
import tempfile
import os
from queuectl.persistence.sqlite_store import SQLiteJobStore
from queuectl.core.job import Job, JobState

class TestSQLiteStorage(unittest.TestCase):
    
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.storage = SQLiteJobStore(self.db_path)
    
    def tearDown(self):
        self.storage.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_save_and_retrieve_job(self):
        job = Job(command="echo hello", job_id="test-job")
        
       
        self.storage.save_job(job)
      
        retrieved = self.storage.get_job("test-job")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test-job")
        self.assertEqual(retrieved.command, "echo hello")
        self.assertEqual(retrieved.state, JobState.PENDING)
    
    def test_get_nonexistent_job(self):
        job = self.storage.get_job("nonexistent")
        self.assertIsNone(job)
    
    def test_get_jobs_by_state(self):
        job1 = Job(command="echo one", job_id="job1")
        job2 = Job(command="echo two", job_id="job2")
        job3 = Job(command="echo three", job_id="job3")
        
        job2.mark_processing()
        job3.mark_completed()
        
        self.storage.save_job(job1)
        self.storage.save_job(job2)
        self.storage.save_job(job3)
        
       
        pending_jobs = self.storage.get_jobs_by_state(JobState.PENDING)
        self.assertEqual(len(pending_jobs), 1)
        self.assertEqual(pending_jobs[0].id, "job1")
        
      
        processing_jobs = self.storage.get_jobs_by_state(JobState.PROCESSING)
        self.assertEqual(len(processing_jobs), 1)
        self.assertEqual(processing_jobs[0].id, "job2")
        
        # Get completed jobs
        completed_jobs = self.storage.get_jobs_by_state(JobState.COMPLETED)
        self.assertEqual(len(completed_jobs), 1)
        self.assertEqual(completed_jobs[0].id, "job3")
    
    def test_get_pending_jobs(self):
        job1 = Job(command="echo one", job_id="job1")
        job2 = Job(command="echo two", job_id="job2")
        job3 = Job(command="echo three", job_id="job3")
        
        job2.mark_failed("Error")
        
        from datetime import datetime, timezone, timedelta
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        job2.next_retry_at = past_time.isoformat()
        
        job3.mark_completed()
        
        self.storage.save_job(job1)
        self.storage.save_job(job2)
        self.storage.save_job(job3)
        
       
        pending_jobs = self.storage.get_pending_jobs()
        self.assertEqual(len(pending_jobs), 2)  
    
    def test_delete_job(self):
        job = Job(command="echo hello", job_id="test-job")
        self.storage.save_job(job)
   
        self.assertIsNotNone(self.storage.get_job("test-job"))
        
       
        self.storage.delete_job("test-job")
        
        # Verify job deleted
        self.assertIsNone(self.storage.get_job("test-job"))
    
    def test_get_all_jobs(self):
        job1 = Job(command="echo one", job_id="job1")
        job2 = Job(command="echo two", job_id="job2")
        
        self.storage.save_job(job1)
        self.storage.save_job(job2)
        
        all_jobs = self.storage.get_all_jobs()
        self.assertEqual(len(all_jobs), 2)
    
    def test_get_job_stats(self):
        job1 = Job(command="echo one", job_id="job1")
        job2 = Job(command="echo two", job_id="job2")
        job3 = Job(command="echo three", job_id="job3")
        job4 = Job(command="echo four", job_id="job4")
        
        job2.mark_processing()
        job3.mark_completed()
        job4.mark_failed("Error")
        
        for job in [job1, job2, job3, job4]:
            self.storage.save_job(job)
        
        stats = self.storage.get_job_stats()
        
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["processing"], 1)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["failed"], 1)
    
    def test_config_management(self):
        
        self.storage.set_config("max_retries", 5)
        self.storage.set_config("backoff_base", 3)
        
       
        max_retries = self.storage.get_config("max_retries")
        backoff_base = self.storage.get_config("backoff_base")
        
        self.assertEqual(max_retries, 5)
        self.assertEqual(backoff_base, 3)
        
       
        nonexistent = self.storage.get_config("nonexistent", "default")
        self.assertEqual(nonexistent, "default")

if __name__ == '__main__':
    unittest.main()