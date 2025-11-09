import json
import time
from datetime import datetime
from typing import Any, Dict, Optional

def format_timestamp(timestamp: str) -> str:
    
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp

def calculate_backoff_delay(attempts: int, base: int = 2) -> int:
    
    return base ** attempts

def validate_job_spec(job_spec: str) -> Dict[str, Any]:
    
    try:
        if job_spec.startswith('{'):
            # JSON specification
            data = json.loads(job_spec)
            if not isinstance(data, dict):
                raise ValueError("Job specification must be a JSON object")
            
            if 'command' not in data:
                raise ValueError("Job must have a 'command' field")
            
            return data
        else:
            # Simple command string
            return {'command': job_spec}
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {str(e)}")

def safe_execute_timeout(func, timeout: int, default: Any = None):
    
    import threading
    from queue import Queue
    
    def wrapper():
        try:
            result_queue.put(func())
        except Exception as e:
            result_queue.put(e)
    
    result_queue = Queue()
    thread = threading.Thread(target=wrapper)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        return default
    
    try:
        result = result_queue.get_nowait()
        if isinstance(result, Exception):
            raise result
        return result
    except:
        return default

def get_command_output(command: str, timeout: int = 30) -> str:
    """Get the output of a shell command with timeout"""
    import subprocess
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout.strip() if result.stdout else ""
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return ""