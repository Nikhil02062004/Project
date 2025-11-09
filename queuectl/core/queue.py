import threading
import time
from typing import List, Optional, Callable
from datetime import datetime

from .job import Job, JobState
from ..persistence.sqlite_store import SQLiteJobStore

class JobQueue:
    def __init__(self, storage: SQLiteJobStore):
        self.storage = storage
        self._lock = threading.RLock()
    
    def enqueue(self, command: str, job_id: Optional[str] = None, max_retries: Optional[int] = None) -> Job:
        with self._lock:
            if max_retries is None:
                max_retries = self.storage.get_config('max_retries', 3)
            
            job = Job(command=command, job_id=job_id, max_retries=max_retries)
            self.storage.save_job(job)
            return job
    
    def dequeue(self) -> Optional[Job]:
        with self._lock:
            pending_jobs = self.storage.get_pending_jobs()
            
            for job in pending_jobs:
                if job.can_process():
                    job.mark_processing()
                    self.storage.save_job(job)
                    return job
            
            return None
    
    def get_job(self, job_id: str) -> Optional[Job]:
        return self.storage.get_job(job_id)
    
    def list_jobs(self, state: Optional[JobState] = None) -> List[Job]:
        if state:
            return self.storage.get_jobs_by_state(state)
        return self.storage.get_all_jobs()
    
    def complete_job(self, job_id: str):
        with self._lock:
            job = self.storage.get_job(job_id)
            if job:
                job.mark_completed()
                self.storage.save_job(job)
    
    def fail_job(self, job_id: str, error: str = ""):
        with self._lock:
            job = self.storage.get_job(job_id)
            if job:
                job.mark_failed(error)
                if job.attempts >= job.max_retries:
                    job.mark_dead()
                self.storage.save_job(job)
    
    def retry_dlq_job(self, job_id: str) -> bool:
        with self._lock:
            job = self.storage.get_job(job_id)
            if job and job.state == JobState.DEAD:
                job.state = JobState.PENDING
                job.attempts = 0
                job.last_error = None
                job.next_retry_at = None
                job.updated_at = job._current_timestamp()
                self.storage.save_job(job)
                return True
            return False
    
    def get_stats(self) -> dict:
        return self.storage.get_job_stats()
    
    def get_dlq_jobs(self) -> List[Job]:
        return self.storage.get_jobs_by_state(JobState.DEAD)