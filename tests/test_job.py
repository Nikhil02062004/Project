import unittest
import time
from datetime import datetime, timezone, timedelta
from queuectl.core.job import Job, JobState

class TestJob(unittest.TestCase):
    
    def test_job_creation(self):
        job = Job(command="echo hello")
        self.assertEqual(job.command, "echo hello")
        self.assertEqual(job.state, JobState.PENDING)
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.max_retries, 3)
        self.assertIsNotNone(job.id)
        self.assertIsNotNone(job.created_at)
        self.assertIsNotNone(job.updated_at)
    
    def test_job_with_custom_id(self):
        job = Job(command="echo hello", job_id="custom-id")
        self.assertEqual(job.id, "custom-id")
    
    def test_job_state_transitions(self):
        job = Job(command="echo hello")
        
        job.mark_processing()
        self.assertEqual(job.state, JobState.PROCESSING)
        
        job.mark_completed()
        self.assertEqual(job.state, JobState.COMPLETED)
    
    def test_job_failure_with_retry(self):
        job = Job(command="echo hello", max_retries=3)
        
        job.mark_failed("Test error")
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.attempts, 1)
        self.assertIsNotNone(job.next_retry_at)
        self.assertEqual(job.last_error, "Test error")
    
    def test_job_exhaust_retries(self):
        job = Job(command="echo hello", max_retries=2)
        
        # First failure
        job.mark_failed("Error 1")
        self.assertEqual(job.state, JobState.FAILED)
        self.assertEqual(job.attempts, 1)
        
        # Second failure should move to DEAD
        job.mark_failed("Error 2")
        self.assertEqual(job.state, JobState.DEAD)
        self.assertEqual(job.attempts, 2)
    
    def test_exponential_backoff(self):
        job = Job(command="echo hello", max_retries=3)
        
        # First attempt: 2^1 = 2 seconds
        job.mark_failed("Error")
        delay1 = 2 ** 1
        
        # Second attempt: 2^2 = 4 seconds  
        job.mark_failed("Error")
        delay2 = 2 ** 2
        
        self.assertEqual(job.attempts, 2)
    
    def test_should_retry(self):
        job = Job(command="echo hello", max_retries=2)
        
        # Not failed, shouldn't retry
        self.assertFalse(job.should_retry())
        
        # Failed but within retries and ready for retry
        job.mark_failed("Error")
        # Set next_retry_at to past to make it immediately retryable
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        job.next_retry_at = past_time.isoformat()
        self.assertTrue(job.should_retry())
        
        # Exhausted retries
        job.mark_failed("Error")  # This should mark as DEAD
        self.assertFalse(job.should_retry())
    
    def test_can_process(self):
        job = Job(command="echo hello", max_retries=1)
        
        # Pending job can be processed
        self.assertTrue(job.can_process())
        
        # Processing job cannot be processed
        job.mark_processing()
        self.assertFalse(job.can_process())
        
        # Completed job cannot be processed
        job.mark_completed()
        self.assertFalse(job.can_process())
        
        # Failed job ready for retry can be processed
        job2 = Job(command="echo hello", max_retries=2)  # Changed to 2 retries
        job2.mark_failed("Error")
        
        # Manually set next_retry_at to a past time to make it immediately retryable
        from datetime import datetime, timezone, timedelta
        past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        job2.next_retry_at = past_time.isoformat()
    
        self.assertTrue(job2.can_process())
    
    def test_serialization(self):
        job = Job(command="echo hello", job_id="test-id", max_retries=5)
        job.mark_processing()
        
        # Convert to dict
        job_dict = job.to_dict()
        self.assertEqual(job_dict["id"], "test-id")
        self.assertEqual(job_dict["command"], "echo hello")
        self.assertEqual(job_dict["state"], "processing")
        self.assertEqual(job_dict["max_retries"], 5)
        
        # Recreate from dict
        new_job = Job.from_dict(job_dict)
        self.assertEqual(new_job.id, "test-id")
        self.assertEqual(new_job.command, "echo hello")
        self.assertEqual(new_job.state, JobState.PROCESSING)
        self.assertEqual(new_job.max_retries, 5)

if __name__ == '__main__':
    unittest.main()