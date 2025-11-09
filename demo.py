import time
import threading
from queuectl.core.queue import JobQueue
from queuectl.core.worker import WorkerManager
from queuectl.persistence.sqlite_store import SQLiteJobStore

def run_demo():
    print("🚀 QueueCTL Demo")
    print("=" * 50)
    
   
    storage = SQLiteJobStore("demo.db")
    queue = JobQueue(storage)
    worker_manager = WorkerManager(queue)
    
  
    print("\n1. Enqueuing jobs...")
    jobs = [
        queue.enqueue("echo 'Hello World'"),
        queue.enqueue("sleep 1 && echo 'Task completed'"),
        queue.enqueue("ls -la"),
    ]
    
    for job in jobs:
        print(f"   - Enqueued: {job.command} (ID: {job.id})")
    
 
    print("\n2. Starting workers...")
    worker_manager.start_workers(2)


    print("\n3. Monitoring progress...")
    for i in range(5):
        time.sleep(1)
        stats = queue.get_stats()
        print(f"   After {i+1}s - Completed: {stats.get('completed', 0)}, "
              f"Pending: {stats.get('pending', 0)}")
    
   
    print("\n4. Testing retry mechanism...")
    failing_job = queue.enqueue("invalid-command-that-fails", max_retries=2)
    print(f"   - Enqueued failing job: {failing_job.id}")
    
    time.sleep(5)
    
    failed_job = queue.get_job(failing_job.id)
    print(f"   - Job state: {failed_job.state.value}, Attempts: {failed_job.attempts}")
    
   
    print("\n5. Dead Letter Queue operations...")
    dlq_jobs = queue.get_dlq_jobs()
    if dlq_jobs:
        print(f"   - DLQ has {len(dlq_jobs)} jobs")
        for job in dlq_jobs:
            print(f"     * {job.id}: {job.command}")
    
   
    print("\n6. Cleaning up...")
    worker_manager.stop_workers()
    storage.close()
    
    print("\n✅ Demo completed!")

if __name__ == '__main__':
    run_demo()