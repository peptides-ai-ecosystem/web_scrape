"""
Simple in-memory job queue for tracking background operations.
No persistence - jobs cleared on server restart.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from app.core.clock import utc_now_naive


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job:
    """Represents a background job."""

    def __init__(self, job_id: str, endpoint: str, parameters: dict[str, Any]):
        self.job_id = job_id
        self.endpoint = endpoint
        self.parameters = parameters
        self.status = JobStatus.PENDING
        self.created_at = utc_now_naive()
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None
        self.result: Any | None = None
        self.error: str | None = None
        self.progress: int = 0  # 0-100

    def start(self):
        self.status = JobStatus.RUNNING
        self.start_time = utc_now_naive()

    def complete(self, result: Any = None):
        self.status = JobStatus.COMPLETED
        self.end_time = utc_now_naive()
        self.result = result

    def fail(self, error: str):
        self.status = JobStatus.FAILED
        self.end_time = utc_now_naive()
        self.error = error

    def cancel(self):
        self.status = JobStatus.CANCELLED
        self.end_time = utc_now_naive()

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary for API responses."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "endpoint": self.endpoint,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
        }


class JobQueue:
    """Simple in-memory job queue."""

    def __init__(self):
        self.jobs: dict[str, Job] = {}

    def create_job(self, endpoint: str, parameters: dict[str, Any]) -> Job:
        """Create and register a new job."""
        job_id = f"{endpoint.replace('/', '_')}_{int(utc_now_naive().timestamp())}_{str(uuid.uuid4())[:8]}"
        job = Job(job_id, endpoint, parameters)
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Job | None:
        """Retrieve a job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(self, status: JobStatus | None = None) -> list[Job]:
        """List jobs, optionally filtered by status."""
        if status:
            return [j for j in self.jobs.values() if j.status == status]
        return list(self.jobs.values())

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if it's pending or running."""
        job = self.get_job(job_id)
        if job and job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            job.cancel()
            return True
        return False

    def cleanup_old_jobs(self, hours: int = 24):
        """Remove completed jobs older than specified hours."""
        cutoff = utc_now_naive().timestamp() - (hours * 3600)
        to_remove = [
            jid
            for jid, job in self.jobs.items()
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
            and job.end_time
            and job.end_time.timestamp() < cutoff
        ]
        for jid in to_remove:
            del self.jobs[jid]


# Global job queue instance
_job_queue = JobQueue()


def get_job_queue() -> JobQueue:
    """Get the global job queue instance."""
    return _job_queue
