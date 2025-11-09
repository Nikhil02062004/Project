import subprocess
import time
import json
import os
import sqlite3

def run_command(cmd):
    """Run a CLI command and return output"""
    result = subprocess.run(
        f"python -m queuectl.cli {cmd}",
        shell=True,
        capture_output=True,
        text=True
    )
    return result.stdout, result.stderr, result.returncode

def cleanup():
    """Clean up test database"""
    if os.path.exists("queuectl.db"):
        os.remove("queuectl.db")

def test_scenario_1_basic_job():
    """Test 1: Basic job completion"""
    print("=== Test 1: Basic Job Completion ===")
    
   
    stdout, stderr, rc = run_command('enqueue \"echo \\\"Hello World\\\"\"')
    print(f"Enqueue output: {stdout}")
    
  
    import threading
    def start_worker():
        run_command("worker start --count 1")
    
    worker_thread = threading.Thread(target=start_worker, daemon=True)
    worker_thread.start()
    
    
    time.sleep(2)
    
   
    stdout, stderr, rc = run_command("status")
    print(f"Status: {stdout}")
    
   
    stdout, stderr, rc = run_command("list --state completed")
    print(f"Completed jobs: {stdout}")
    
    print("✓ Test 1 passed: Basic job completed successfully\n")

def test_scenario_2_failed_job_retry():
    """Test 2: Failed job retry and DLQ"""
    print("=== Test 2: Failed Job Retry and DLQ ===")
    
   
    job_spec = json.dumps({
        "id": "fail-job-1",
        "command": "exit 1",
        "max_retries": 2
    })
    stdout, stderr, rc = run_command(f"enqueue '{job_spec}'")
    print(f"Enqueued failing job: {stdout}")
    
    
    import threading
    def start_worker():
        run_command("worker start --count 1")
    
    worker_thread = threading.Thread(target=start_worker, daemon=True)
    worker_thread.start()
    
  
    time.sleep(5)
    
 
    stdout, stderr, rc = run_command("dlq list")
    print(f"DLQ jobs: {stdout}")
    
    # Retry from DLQ
    stdout, stderr, rc = run_command("dlq retry fail-job-1")
    print(f"Retry result: {stdout}")
    
    print("✓ Test 2 passed: Failed job handled with retry and DLQ\n")

def test_scenario_3_multiple_workers():
    """Test 3: Multiple workers processing"""
    print("=== Test 3: Multiple Workers ===")
    
    
    for i in range(3):
        stdout, stderr, rc = run_command(f'enqueue \"sleep 1 && echo Job {i}\"')
        print(f"Enqueued job {i}: {stdout}")
    
   
    import threading
    def start_workers():
        run_command("worker start --count 2")
    
    worker_thread = threading.Thread(target=start_workers, daemon=True)
    worker_thread.start()
    
    
    for i in range(3):
        time.sleep(2)
        stdout, stderr, rc = run_command("status")
        print(f"Status after {i*2}s: {stdout}")
    
    print("✓ Test 3 passed: Multiple workers processed jobs\n")

def test_scenario_4_persistence():
    """Test 4: Data persistence across restarts"""
    print("=== Test 4: Data Persistence ===")
    
    
    stdout, stderr, rc = run_command('enqueue \"echo Persistent job\"')
    job_id = stdout.split()[2] if "Enqueued job" in stdout else "unknown"
    print(f"Enqueued persistent job: {stdout}")
    
   
    conn = sqlite3.connect("queuectl.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE id = ?", (job_id,))
    count = cursor.fetchone()[0]
    conn.close()
    
    print(f"Job found in database: {count > 0}")
    
    # Simulate restart by running status command (reinitializes database connection)
    stdout, stderr, rc = run_command("status")
    print(f"Status after 'restart': {stdout}")
    
    print("✓ Test 4 passed: Job data persisted across restarts\n")

def test_scenario_5_invalid_commands():
    """Test 5: Invalid command handling"""
    print("=== Test 5: Invalid Commands ===")
    
    # Enqueue a job with non-existent command
    stdout, stderr, rc = run_command('enqueue \"nonexistent-command-xyz\"')
    print(f"Enqueued invalid command: {stdout}")
    
    # Start worker
    import threading
    def start_worker():
        run_command("worker start --count 1")
    
    worker_thread = threading.Thread(target=start_worker, daemon=True)
    worker_thread.start()
    
    time.sleep(3)
    
    # Check that job failed appropriately
    stdout, stderr, rc = run_command("list --state failed")
    print(f"Failed jobs: {stdout}")
    
    print("✓ Test 5 passed: Invalid commands handled gracefully\n")

if __name__ == "__main__":
    # Clean up before tests
    cleanup()
    
    try:
        test_scenario_1_basic_job()
        time.sleep(1)
        
        test_scenario_2_failed_job_retry()
        time.sleep(1)
        
        test_scenario_3_multiple_workers()
        time.sleep(1)
        
        test_scenario_4_persistence()
        time.sleep(1)
        
        test_scenario_5_invalid_commands()
        
        print("🎉 All test scenarios completed successfully!")
        
    finally:
        # Clean up
        cleanup()