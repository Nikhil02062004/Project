import sqlite3
import json
import threading
import atexit
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from ..core.job import Job, JobState

class SQLiteJobStore:
    def __init__(self, db_path: str = "queuectl.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._connections = set()
        self._init_db()
        atexit.register(self.close_all)
    
    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'connection'):
            conn = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=30.0
            )
            conn.row_factory = sqlite3.Row
            self._local.connection = conn
            self._connections.add(conn)
        return self._local.connection
    
    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_error TEXT,
                next_retry_at TEXT
            )
        ''')
        
        # Configuration table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # Insert default configuration
        cursor.execute('''
            INSERT OR IGNORE INTO config (key, value) 
            VALUES ('max_retries', '3'), ('backoff_base', '2')
        ''')
        
        # Index for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_jobs_next_retry ON jobs(next_retry_at)
        ''')
        
        conn.commit()
    
    def save_job(self, job: Job):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO jobs 
            (id, command, state, attempts, max_retries, created_at, updated_at, last_error, next_retry_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job.id, job.command, job.state.value, job.attempts, 
            job.max_retries, job.created_at, job.updated_at, 
            job.last_error, job.next_retry_at
        ))
        
        conn.commit()
    
    def get_job(self, job_id: str) -> Optional[Job]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_job(row)
        return None
    
    def get_jobs_by_state(self, state: JobState, limit: Optional[int] = None) -> List[Job]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM jobs WHERE state = ? ORDER BY created_at'
        if limit:
            query += f' LIMIT {limit}'
            
        cursor.execute(query, (state.value,))
        return [self._row_to_job(row) for row in cursor.fetchall()]
    
    def get_pending_jobs(self) -> List[Job]:
        """Get jobs that are ready to be processed (pending or ready for retry)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        current_time = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            SELECT * FROM jobs 
            WHERE state = ? OR (state = ? AND (next_retry_at IS NULL OR next_retry_at <= ?))
            ORDER BY created_at
        ''', (JobState.PENDING.value, JobState.FAILED.value, current_time))
        
        return [self._row_to_job(row) for row in cursor.fetchall()]
    
    def delete_job(self, job_id: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
        conn.commit()
    
    def get_all_jobs(self) -> List[Job]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM jobs ORDER BY created_at')
        return [self._row_to_job(row) for row in cursor.fetchall()]
    
    def get_job_stats(self) -> Dict[str, int]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT state, COUNT(*) as count FROM jobs GROUP BY state
        ''')
        
        stats = {state.value: 0 for state in JobState}
        for row in cursor.fetchall():
            stats[row['state']] = row['count']
        
        return stats
    
    def _row_to_job(self, row) -> Job:
        job_data = {
            "id": row["id"],
            "command": row["command"],
            "state": JobState(row["state"]),
            "attempts": row["attempts"],
            "max_retries": row["max_retries"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_error": row["last_error"]
        }
        if row["next_retry_at"]:
            job_data["next_retry_at"] = row["next_retry_at"]
        
        return Job.from_dict(job_data)
    
    # Configuration methods
    def get_config(self, key: str, default: Any = None) -> Any:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
        row = cursor.fetchone()
        
        if row:
            try:
                return json.loads(row['value'])
            except json.JSONDecodeError:
                return row['value']
        return default
    
    def set_config(self, key: str, value: Any):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)',
            (key, json.dumps(value))
        )
        conn.commit()
    
    def close(self):
        if hasattr(self._local, 'connection'):
            conn = self._local.connection
            conn.close()
            self._connections.discard(conn)
            del self._local.connection
    
    def close_all(self):
        """Close all database connections"""
        for conn in list(self._connections):
            try:
                conn.close()
            except:
                pass
        self._connections.clear()