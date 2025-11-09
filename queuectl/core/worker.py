import subprocess
import threading
import time
import signal
import sys
import os
from typing import List, Optional
from datetime import datetime

from .queue import JobQueue
from .job import Job

class Worker:
    def __init__(self, queue: JobQueue, worker_id: str):
        self.queue = queue
        self.worker_id = worker_id
        self._running = False
        self._current_job: Optional[Job] = None
        self._thread: Optional[threading.Thread] = None
        
    def start(self):
        """Start the worker in a background thread"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the worker gracefully"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=30)  # Wait up to 30 seconds
    
    def _run(self):
        """Main worker loop"""
        while self._running:
            job = self.queue.dequeue()
            
            if job:
                self._current_job = job
                self._process_job(job)
                self._current_job = None
            else:
                # No jobs available, sleep a bit
                time.sleep(1)
    
    def _process_job(self, job: Job):
        """Execute a job command and handle the result"""
        try:
            # Execute the command
            result = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Success
                self.queue.complete_job(job.id)
                print(f"Worker {self.worker_id}: Job {job.id} completed successfully")
            else:
                # Command failed
                error_msg = f"Exit code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                self.queue.fail_job(job.id, error_msg)
                print(f"Worker {self.worker_id}: Job {job.id} failed: {error_msg}")
                
        except subprocess.TimeoutExpired:
            self.queue.fail_job(job.id, "Command timed out after 5 minutes")
            print(f"Worker {self.worker_id}: Job {job.id} timed out")
            
        except Exception as e:
            self.queue.fail_job(job.id, str(e))
            print(f"Worker {self.worker_id}: Job {job.id} error: {str(e)}")
    
    def is_working(self) -> bool:
        return self._current_job is not None

class WorkerManager:
    def __init__(self, queue: JobQueue):
        self.queue = queue
        self.workers: List[Worker] = []
        self._running = False
        
    def start_workers(self, count: int = 1):
        """Start multiple workers"""
        if self._running:
            self.stop_workers()
        
        self._running = True
        self.workers = []
        
        for i in range(count):
            worker = Worker(self.queue, f"worker-{i+1}")
            worker.start()
            self.workers.append(worker)
        
        print(f"Started {count} worker(s)")
    
    def stop_workers(self):
        """Stop all workers gracefully"""
        self._running = False
        for worker in self.workers:
            worker.stop()
        self.workers = []
        print("All workers stopped")
    
    def get_active_workers(self) -> List[Worker]:
        return [w for w in self.workers if w._thread and w._thread.is_alive()]
    
    def get_worker_stats(self) -> dict:
        active_workers = self.get_active_workers()
        working_workers = [w for w in active_workers if w.is_working()]
        
        return {
            "total": len(active_workers),
            "working": len(working_workers),
            "idle": len(active_workers) - len(working_workers)
        }