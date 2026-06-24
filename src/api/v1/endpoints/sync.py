from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os

from src.core.scheduler import start_scheduler, pause_scheduler, resume_scheduler, get_scheduler_status
from typing import List, Optional
import os

from src.utils.crawl_peptide_urls import crawl_peptide_urls
from src.services.scraper_manager import ScraperManager
from src.infrastructure.csv_storage import CSVStorage
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.mappers.graph_import_orchestrator import GraphImportOrchestrator
from src.utils.error_tracker import ErrorTracker
from src.config import log_debug, log_error, OUTPUT_DIR
from src.core.job_queue import get_job_queue, JobStatus

router = APIRouter()


class SyncRequest(BaseModel):
    limit: Optional[int] = None
    urls: Optional[List[str]] = None  # If None or empty → auto-discover via URL crawl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_urls(requested_urls: Optional[List[str]], limit: Optional[int]) -> List[str]:
    """
    Resolve the final list of URLs to scrape.
    - If caller provides a non-empty list, use those directly.
    - Otherwise auto-discover via crawl_peptide_urls().
    - Apply limit cap after resolving.
    """
    if requested_urls:
        urls = requested_urls
        log_debug(f"Using {len(urls)} caller-provided URLs", "sync_endpoint")
    else:
        log_debug("No URLs provided — auto-discovering via URL crawl", "sync_endpoint")
        urls = crawl_peptide_urls()

    if limit and limit > 0:
        urls = urls[:limit]

    return urls


# ---------------------------------------------------------------------------
# Core Sync (Scrape → Core DB Tables)
# ---------------------------------------------------------------------------

def run_core_sync_task(job_id: str, requested_urls: Optional[List[str]], limit: Optional[int], db_url: str):
    """
    Background task: discover/resolve URLs → scrape → sync to core DB tables.
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    tracker = ErrorTracker()

    try:
        # Step 1: Resolve URLs
        urls = _resolve_urls(requested_urls, limit)
        if not urls:
            job.fail("No URLs discovered or provided. Sync aborted.")
            return

        log_debug(f"Core sync starting scrape for {len(urls)} URLs", "sync_endpoint")

        # Step 2: Scrape → writes to MASTER_CSV
        manager = ScraperManager()
        manager.run(urls, tracker=tracker, cancel_check=lambda: job.status == JobStatus.CANCELLED)

        if job.status == JobStatus.CANCELLED:
            log_debug("Job cancelled during scraping. Aborting DB sync.", "sync_endpoint")
            return

        # Step 3: Read scraped data from CSV
        csv_store = CSVStorage()
        rows = csv_store.read()

        if not rows:
            log_debug("Scrape produced no rows. Completing with 0 rows synced.", "sync_endpoint")
            job.complete({
                "urls_scraped": len(urls),
                "rows_synced": 0,
                "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                "db_errors": 0,
            })
            return

        # Step 4: Sync to core DB tables
        orchestrator = DbImportOrchestrator()
        orchestrator.sync_to_db(db_url, rows, tracker=tracker)

        job.complete({
            "urls_scraped": len(urls),
            "rows_synced": len(rows),
            "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
            "db_errors": len(tracker.db_errors) if tracker.has_errors() else 0,
        })

    except Exception as e:
        log_error(f"Fatal error during core sync task: {e}", "sync_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_core_sync.json")
            tracker.print_summary()


# ---------------------------------------------------------------------------
# Graph Sync (Scrape → Graph DB Tables)
# ---------------------------------------------------------------------------

def run_graph_sync_task(job_id: str, requested_urls: Optional[List[str]], limit: Optional[int], db_url: str):
    """
    Background task: discover/resolve URLs → scrape → sync to graph DB tables.
    Only processes graph data for peptides that already exist in the database.
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    tracker = ErrorTracker()

    try:
        # Step 1: Resolve URLs
        urls = _resolve_urls(requested_urls, limit)
        if not urls:
            job.fail("No URLs discovered or provided. Sync aborted.")
            return

        log_debug(f"Graph sync starting scrape for {len(urls)} URLs", "sync_endpoint")

        # Step 2: Scrape → writes to MASTER_CSV
        manager = ScraperManager()
        manager.run(urls, tracker=tracker, cancel_check=lambda: job.status == JobStatus.CANCELLED)

        if job.status == JobStatus.CANCELLED:
            log_debug("Job cancelled during scraping. Aborting DB sync.", "sync_endpoint")
            return

        # Step 3: Read scraped data from CSV
        csv_store = CSVStorage()
        rows = csv_store.read()

        if not rows:
            log_debug("Scrape produced no rows. Completing with 0 rows processed.", "sync_endpoint")
            job.complete({
                "urls_scraped": len(urls),
                "rows_processed": 0,
                "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                "db_errors": 0,
            })
            return

        # Step 4: Sync to graph DB tables
        orchestrator = GraphImportOrchestrator()
        orchestrator.sync_graph_data(db_url, rows, tracker=tracker)

        job.complete({
            "urls_scraped": len(urls),
            "rows_processed": len(rows),
            "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
            "db_errors": len(tracker.db_errors) if tracker.has_errors() else 0,
        })

    except Exception as e:
        log_error(f"Fatal error during graph sync task: {e}", "sync_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_graph_sync.json")
            tracker.print_summary()


def run_graph_sync_missing_task(job_id: str, requested_urls: Optional[List[str]], limit: Optional[int], db_url: str):
    """
    Background task: discover/resolve URLs → scrape → sync to graph DB tables (only if missing).
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    tracker = ErrorTracker()

    try:
        # Step 1: Resolve URLs
        urls = _resolve_urls(requested_urls, limit)
        if not urls:
            job.fail("No URLs discovered or provided. Sync aborted.")
            return

        log_debug(f"Graph Missing sync starting scrape for {len(urls)} URLs", "sync_endpoint")

        # Step 2: Scrape → writes to MASTER_CSV
        manager = ScraperManager()
        manager.run(urls, tracker=tracker, cancel_check=lambda: job.status == JobStatus.CANCELLED)

        if job.status == JobStatus.CANCELLED:
            log_debug("Job cancelled during scraping. Aborting DB sync.", "sync_endpoint")
            return

        # Step 3: Read scraped data from CSV
        csv_store = CSVStorage()
        rows = csv_store.read()

        if not rows:
            log_debug("Scrape produced no rows. Completing with 0 rows processed.", "sync_endpoint")
            job.complete({
                "urls_scraped": len(urls),
                "rows_processed": 0,
                "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                "db_errors": 0,
            })
            return

        # Step 4: Sync to graph DB tables
        orchestrator = GraphImportOrchestrator()
        orchestrator.sync_graph_missing_data(db_url, rows, tracker=tracker)

        job.complete({
            "urls_scraped": len(urls),
            "rows_processed": len(rows),
            "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
            "db_errors": len(tracker.db_errors) if tracker.has_errors() else 0,
        })

    except Exception as e:
        log_error(f"Fatal error during graph missing sync task: {e}", "sync_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_graph_missing_sync.json")
            tracker.print_summary()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/core")
async def start_core_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    Scrape peptide data (auto-discover or targeted URLs) then sync to core DB tables.

    - **urls**: Optional list of specific URLs to scrape. If omitted, URLs are
      auto-discovered via the peptide URL crawler.
    - **limit**: Optional cap on the number of URLs to scrape.

    Returns a `job_id` for tracking progress via `/operations/job/{job_id}`.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")

    queue = get_job_queue()
    job = queue.create_job("/sync/core", {
        "limit": request.limit,
        "urls_provided": len(request.urls) if request.urls else 0,
        "mode": "targeted" if request.urls else "auto-discover",
    })
    background_tasks.add_task(run_core_sync_task, job.job_id, request.urls, request.limit, db_url)

    return job.to_dict()


@router.post("/graph")
async def start_graph_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    Scrape peptide data (auto-discover or targeted URLs) then sync to graph DB tables.

    Only syncs graph data for peptides already present in the database.

    - **urls**: Optional list of specific URLs to scrape. If omitted, URLs are
      auto-discovered via the peptide URL crawler.
    - **limit**: Optional cap on the number of URLs to scrape.

    Returns a `job_id` for tracking progress via `/operations/job/{job_id}`.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")

    queue = get_job_queue()
    job = queue.create_job("/sync/graph", {
        "limit": request.limit,
        "urls_provided": len(request.urls) if request.urls else 0,
        "mode": "targeted" if request.urls else "auto-discover",
    })
    background_tasks.add_task(run_graph_sync_task, job.job_id, request.urls, request.limit, db_url)

    return job.to_dict()


@router.post("/graph-missing")
async def start_graph_sync_missing(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    Scrape peptide data then sync to graph DB tables only if missing.

    Only syncs graph data for peptides already present in the database 
    AND where the specific administration method graph data is missing.

    - **urls**: Optional list of specific URLs to scrape.
    - **limit**: Optional cap on the number of URLs to scrape.

    Returns a `job_id` for tracking progress via `/operations/job/{job_id}`.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")

    queue = get_job_queue()
    job = queue.create_job("/sync/graph-missing", {
        "limit": request.limit,
        "urls_provided": len(request.urls) if request.urls else 0,
        "mode": "targeted" if request.urls else "auto-discover",
    })
    background_tasks.add_task(run_graph_sync_missing_task, job.job_id, request.urls, request.limit, db_url)

    return job.to_dict()


# ---------------------------------------------------------------------------
# Scheduler Config Endpoints
# ---------------------------------------------------------------------------

class SchedulerConfigRequest(BaseModel):
    interval_hours: Optional[float] = 24.0

@router.get("/scheduler/status")
async def get_sync_scheduler_status():
    """
    Get the status of the combined background sync scheduler.
    """
    return get_scheduler_status()

@router.post("/scheduler/start")
async def start_sync_scheduler(config: SchedulerConfigRequest):
    """
    Start or re-configure the combined background sync scheduler.
    """
    start_scheduler(interval_hours=config.interval_hours)
    return {"message": "Scheduler started/configured", "interval_hours": config.interval_hours}

@router.post("/scheduler/pause")
async def pause_sync_scheduler():
    """
    Pause the background sync scheduler.
    """
    pause_scheduler()
    return {"message": "Scheduler paused"}

@router.post("/scheduler/resume")
async def resume_sync_scheduler():
    """
    Resume the background sync scheduler.
    """
    resume_scheduler()
    return {"message": "Scheduler resumed"}
