"""Background job queries for ``/api/v1/operations`` (the in-memory job queue)."""
from typing import Any, Dict, Optional

from src.core.errors import BadRequestError, NotFoundError
from src.core.job_queue import JobStatus, get_job_queue


def list_jobs(status: Optional[str] = None) -> Dict[str, Any]:
    """Every job in the queue, optionally filtered by status; 400 for an unknown status."""
    queue = get_job_queue()

    try:
        filter_status = JobStatus(status) if status else None
    except ValueError:
        raise BadRequestError(
            f"Invalid status '{status}'. Must be one of: {', '.join([s.value for s in JobStatus])}"
        )

    jobs = queue.list_jobs(filter_status)
    return {
        "count": len(jobs),
        "status_filter": status,
        "jobs": [job.to_dict() for job in jobs],
    }


def get_job(job_id: str) -> Dict[str, Any]:
    """One job's full record; 404 when unknown."""
    job = get_job_queue().get_job(job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    return job.to_dict()


def cancel_job(job_id: str) -> Dict[str, Any]:
    """Cancel a pending or running job; 404 when unknown, 400 when already finished."""
    job = get_job_queue().get_job(job_id)

    if not job:
        raise NotFoundError(f"Job {job_id} not found")

    if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise BadRequestError(
            f"Cannot cancel job in '{job.status.value}' status. "
            f"Only 'pending' or 'running' jobs can be cancelled."
        )

    job.cancel()
    return {
        "message": f"Job {job_id} cancelled",
        "job": job.to_dict(),
    }


def health() -> Dict[str, Any]:
    """Always "healthy" while the process answers, plus job counts by status."""
    jobs = get_job_queue().list_jobs()

    stats = {
        "pending": len([j for j in jobs if j.status == JobStatus.PENDING]),
        "running": len([j for j in jobs if j.status == JobStatus.RUNNING]),
        "completed": len([j for j in jobs if j.status == JobStatus.COMPLETED]),
        "failed": len([j for j in jobs if j.status == JobStatus.FAILED]),
        "cancelled": len([j for j in jobs if j.status == JobStatus.CANCELLED]),
    }

    return {
        "status": "healthy",
        "total_jobs": len(jobs),
        "stats": stats,
    }
