from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os

from src.infrastructure.csv_storage import CSVStorage
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.mappers.graph_import_orchestrator import GraphImportOrchestrator
from src.utils.error_tracker import ErrorTracker
from src.config import log_debug, log_error, OUTPUT_DIR
from src.core.job_queue import get_job_queue

router = APIRouter()

class SyncRequest(BaseModel):
    limit: Optional[int] = None


def run_core_sync_task(job_id: str, limit: Optional[int], db_url: str):
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return
    
    job.start()
    csv_store = CSVStorage()
    rows = csv_store.read()
    if limit:
        rows = rows[:limit]

    tracker = ErrorTracker()
    orchestrator = DbImportOrchestrator()
    try:
        orchestrator.sync_to_db(db_url, rows, tracker=tracker)
        job.complete({
            "rows_synced": len(rows),
            "errors": len(tracker.db_errors) if tracker.has_errors() else 0
        })
    except Exception as e:
        log_error(f"Fatal error during core sync task: {e}", "sync_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_core_sync.json")


def run_graph_sync_task(job_id: str, limit: Optional[int], db_url: str):
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return
    
    job.start()
    csv_store = CSVStorage()
    rows = csv_store.read()
    if limit:
        rows = rows[:limit]

    tracker = ErrorTracker()
    orchestrator = GraphImportOrchestrator()
    try:
        orchestrator.sync_graph_data(db_url, rows, tracker=tracker)
        job.complete({
            "rows_processed": len(rows),
            "errors": len(tracker.db_errors) if tracker.has_errors() else 0
        })
    except Exception as e:
        log_error(f"Fatal error during graph sync task: {e}", "sync_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_graph_sync.json")


@router.post("/core")
async def start_core_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """Core Database Sync (non-graph table data). Returns job_id for tracking."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")
    
    queue = get_job_queue()
    job = queue.create_job("/sync/core", {"limit": request.limit})
    background_tasks.add_task(run_core_sync_task, job.job_id, request.limit, db_url)
    
    return job.to_dict()


@router.post("/graph")
async def start_graph_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """Graph Data Database Sync (isolated from core data). Returns job_id for tracking."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")
    
    queue = get_job_queue()
    job = queue.create_job("/sync/graph", {"limit": request.limit})
    background_tasks.add_task(run_graph_sync_task, job.job_id, request.limit, db_url)
    
    return job.to_dict()
