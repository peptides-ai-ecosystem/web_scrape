"""
Operations and job management endpoints.
"""
from fastapi import APIRouter, HTTPException
from src.core.job_queue import get_job_queue, JobStatus

router = APIRouter()


@router.get("/jobs")
async def list_jobs(status: str = None):
    """
    List all jobs, optionally filtered by status.
    Status options: pending, running, completed, failed, cancelled
    """
    queue = get_job_queue()
    
    try:
        filter_status = JobStatus(status) if status else None
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join([s.value for s in JobStatus])}"
        )
    
    jobs = queue.list_jobs(filter_status)
    return {
        "count": len(jobs),
        "status_filter": status,
        "jobs": [job.to_dict() for job in jobs]
    }


@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get detailed status of a specific job."""
    queue = get_job_queue()
    job = queue.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return job.to_dict()


@router.delete("/job/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running or pending job."""
    queue = get_job_queue()
    job = queue.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in {job.status.value} status"
        )
    
    job.cancel()
    return {
        "message": f"Job {job_id} cancelled",
        "job": job.to_dict()
    }


@router.get("/health")
async def system_health():
    """Get system health and job queue statistics."""
    queue = get_job_queue()
    jobs = queue.list_jobs()
    
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
        "stats": stats
    }
