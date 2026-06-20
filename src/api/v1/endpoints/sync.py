from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os

from src.infrastructure.csv_storage import CSVStorage
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.mappers.graph_import_orchestrator import GraphImportOrchestrator
from src.utils.error_tracker import ErrorTracker
from src.config import log_debug, log_error, OUTPUT_DIR

router = APIRouter()

class SyncRequest(BaseModel):
    limit: Optional[int] = None


def run_core_sync_task(limit: Optional[int], db_url: str):
    csv_store = CSVStorage()
    rows = csv_store.read()
    if limit is not None:
        rows = rows[:limit]

    tracker = ErrorTracker()
    orchestrator = DbImportOrchestrator()
    try:
        orchestrator.sync_to_db(db_url, rows, tracker=tracker)
    except Exception as e:
        log_error(f"Fatal error during core sync task: {e}", "sync_endpoint")
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_core_sync.json")


def run_graph_sync_task(limit: Optional[int], db_url: str):
    csv_store = CSVStorage()
    rows = csv_store.read()
    if limit is not None:
        rows = rows[:limit]

    tracker = ErrorTracker()
    orchestrator = GraphImportOrchestrator()
    try:
        orchestrator.sync_graph_data(db_url, rows, tracker=tracker)
    except Exception as e:
        log_error(f"Fatal error during graph sync task: {e}", "sync_endpoint")
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_graph_sync.json")


@router.post("/core")
async def start_core_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")
        
    background_tasks.add_task(run_core_sync_task, request.limit, db_url)
    return {"message": "Core Database Sync started in the background", "limit": request.limit}


@router.post("/graph")
async def start_graph_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")
        
    background_tasks.add_task(run_graph_sync_task, request.limit, db_url)
    return {"message": "Graph Data Database Sync started in the background", "limit": request.limit}
