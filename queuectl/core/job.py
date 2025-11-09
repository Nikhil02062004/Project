import uuid
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any

class JobState(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"

class Job:
    def __init__(
        self,
        command: str,
        job_id: Optional[str] = None,
        max_retries: int = 3,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        state: JobState = JobState.PENDING,
        attempts: int = 0,
        last_error: Optional[str] = None
    ):
        self.id = job_id or str(uuid.uuid4())
        self.command = command
        self.state = state
        self.attempts = attempts
        self.max_retries = max_retries
        self.created_at = created_at or self._current_timestamp()
        self.updated_at = updated_at or self._current_timestamp()
        self.last_error = last_error
        self.next_retry_at: Optional[str] = None
        
    def _current_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "state": self.state.value,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_error": self.last_error,
            "next_retry_at": self.next_retry_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        job = cls(
            command=data["command"],
            job_id=data["id"],
            max_retries=data.get("max_retries", 3),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            state=JobState(data["state"]),
            attempts=data.get("attempts", 0),
            last_error=data.get("last_error")
        )
        job.next_retry_at = data.get("next_retry_at")
        return job
    
    def mark_processing(self):
        self.state = JobState.PROCESSING
        self.updated_at = self._current_timestamp()
    
    def mark_completed(self):
        self.state = JobState.COMPLETED
        self.updated_at = self._current_timestamp()
    
    def mark_failed(self, error: str = "", immediate_retry: bool = False):
        """Mark job as failed with optional immediate retry for testing"""
        self.attempts += 1
        self.last_error = error
        self.updated_at = self._current_timestamp()
        
        if self.attempts >= self.max_retries:
            self.state = JobState.DEAD
            self.next_retry_at = None
        else:
            self.state = JobState.FAILED
            # Calculate next retry with exponential backoff
            backoff_seconds = 2 ** self.attempts  # base^attempts
            
            if immediate_retry:
                # For testing: set retry to past so it's immediately available
                next_retry = datetime.now(timezone.utc).timestamp() - 1
            else:
                next_retry = datetime.now(timezone.utc).timestamp() + backoff_seconds
                
            self.next_retry_at = datetime.fromtimestamp(next_retry, timezone.utc).isoformat()
    
    def mark_dead(self):
        self.state = JobState.DEAD
        self.updated_at = self._current_timestamp()
        self.next_retry_at = None
    
    def should_retry(self) -> bool:
        if self.state != JobState.FAILED:
            return False
        
        if self.attempts >= self.max_retries:
            return False
        
        if self.next_retry_at:
            try:
                next_retry = datetime.fromisoformat(self.next_retry_at.replace('Z', '+00:00'))
                return datetime.now(timezone.utc) >= next_retry
            except ValueError:
                return True
        
        return True
    
    def can_process(self) -> bool:
        return (self.state == JobState.PENDING or 
                (self.state == JobState.FAILED and self.should_retry()))