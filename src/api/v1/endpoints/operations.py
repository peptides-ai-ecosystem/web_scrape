"""
Operations and job management endpoints.

All long-running operations (sync, evaluation) run as background tasks and
return a job ID immediately. Use these endpoints to track progress, cancel
stuck jobs, and monitor system health.
"""
from fastapi import APIRouter, HTTPException, Query
from src.core.job_queue import get_job_queue, JobStatus

router = APIRouter()


@router.get(
    "/jobs",
    responses={
        200: {
            "description": "List of jobs matching the optional status filter.",
            "content": {
                "application/json": {
                    "example": {
                        "count": 2,
                        "status_filter": "running",
                        "jobs": [
                            {
                                "job_id": "/sync/core_1742000000_a1b2c3d4",
                                "status": "running",
                                "endpoint": "/sync/core",
                                "parameters": {"limit": 5, "urls_provided": 0, "mode": "auto-discover"},
                                "created_at": "2025-03-15T10:30:00",
                                "start_time": "2025-03-15T10:30:01",
                                "end_time": None,
                                "result": None,
                                "error": None,
                                "progress": 45,
                            }
                        ],
                    }
                }
            },
        },
        400: {"description": "Invalid `status` filter value."},
    },
)
async def list_jobs(
    status: str = Query(
        None,
        description="Filter by job status. Valid values:\n"
                    "- `pending` — queued, not yet started\n"
                    "- `running` — currently executing\n"
                    "- `completed` — finished successfully\n"
                    "- `failed` — terminated with an error\n"
                    "- `cancelled` — aborted by user",
        examples=["running", "completed", "failed"],
    ),
):
    """
    📋 List background jobs, optionally filtered by status.

    Returns all jobs in the in-memory queue. Jobs are **not persisted** across
    server restarts — the queue is cleared when the API server stops.

    ### Query Parameters
    - `status` — optional filter: `pending`, `running`, `completed`, `failed`, `cancelled`.

    ### Errors
    - **400** — Invalid status value (must be one of the allowed enum values).
    """
    queue = get_job_queue()

    try:
        filter_status = JobStatus(status) if status else None
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of: {', '.join([s.value for s in JobStatus])}",
        )

    jobs = queue.list_jobs(filter_status)
    return {
        "count": len(jobs),
        "status_filter": status,
        "jobs": [job.to_dict() for job in jobs],
    }


@router.get(
    "/job/{job_id}",
    responses={
        200: {
            "description": "Full job details including status, parameters, result or error.",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "/sync/core_1742000000_a1b2c3d4",
                        "status": "completed",
                        "endpoint": "/sync/core",
                        "parameters": {"limit": 5, "urls_provided": 0, "mode": "auto-discover"},
                        "created_at": "2025-03-15T10:30:00",
                        "start_time": "2025-03-15T10:30:01",
                        "end_time": "2025-03-15T10:35:22",
                        "result": {"urls_scraped": 5, "rows_synced": 5, "scrape_errors": 0, "db_errors": 0},
                        "error": None,
                        "progress": 100,
                    }
                }
            },
        },
        404: {"description": "No job found with the given ID."},
    },
)
async def get_job_status(job_id: str):
    """
    🔍 Get detailed status and result of a specific background job.

    Poll this endpoint to track progress after starting a sync or evaluation.
    Jobs are automatically cleaned up after 24 hours.

    ### Path Parameters
    - `job_id` — the job ID returned by a sync or evaluation endpoint.

    ### Errors
    - **404** — Job ID not found (may have already been cleaned up).
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job.to_dict()


@router.delete(
    "/job/{job_id}",
    responses={
        200: {
            "description": "Job successfully cancelled.",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Job /sync/core_1742000000_a1b2c3d4 cancelled",
                        "job": {
                            "job_id": "/sync/core_1742000000_a1b2c3d4",
                            "status": "cancelled",
                            "endpoint": "/sync/core",
                            "parameters": {"limit": 5, "urls_provided": 0, "mode": "auto-discover"},
                            "progress": 60,
                        },
                    }
                }
            },
        },
        400: {"description": "Job cannot be cancelled (not in pending or running state)."},
        404: {"description": "Job not found."},
    },
)
async def cancel_job(job_id: str):
    """
    🛑 Cancel a running or pending background job.

    Only jobs in `pending` or `running` state can be cancelled. Once cancelled,
    the scraping loop checks the cancellation flag and stops at the next opportunity.

    ### Path Parameters
    - `job_id` — the job ID to cancel.

    ### Errors
    - **400** — Job is already in `completed`, `failed`, or `cancelled` state.
    - **404** — Job ID not found.
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in '{job.status.value}' status. "
                   f"Only 'pending' or 'running' jobs can be cancelled.",
        )

    job.cancel()
    return {
        "message": f"Job {job_id} cancelled",
        "job": job.to_dict(),
    }


@router.get(
    "/health",
    responses={
        200: {
            "description": "System is healthy with job queue statistics.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "total_jobs": 10,
                        "stats": {
                            "pending": 2,
                            "running": 1,
                            "completed": 5,
                            "failed": 1,
                            "cancelled": 1,
                        },
                    }
                }
            },
        }
    },
)
async def system_health():
    """
    ❤️ System health check and job queue statistics.

    Lightweight endpoint that returns:
    - **status**: always `"healthy"` if the server is reachable
    - **total_jobs**: total jobs tracked since server start
    - **stats**: breakdown by status (pending, running, completed, failed, cancelled)

    Use for monitoring and load-balancer health probes.
    """
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
        "stats": stats,
    }
