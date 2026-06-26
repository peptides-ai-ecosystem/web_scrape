from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError
import os

from src.utils.crawl_peptide_urls import crawl_peptide_urls
from src.services.scraper_manager import ScraperManager
from src.infrastructure.csv_storage import CSVStorage
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.mappers.graph_import_orchestrator import GraphImportOrchestrator
from src.utils.error_tracker import ErrorTracker
from src.config import log_debug, log_error, OUTPUT_DIR

# Keep a global instance of the scheduler
scheduler = AsyncIOScheduler()
SYNC_JOB_ID = "scheduled_combined_sync"

def run_combined_sync_job(limit: int | None = None):
    """
    The background task that performs discovery, scraping, core sync, and graph missing sync.
    Runs in a separate thread so it won't block the FastAPI event loop.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        log_error("DATABASE_URL not configured for scheduled sync.", "scheduler")
        return

    tracker = ErrorTracker()
    try:
        log_debug("Starting scheduled combined sync...", "scheduler")
        
        # 1. Discover URLs
        urls = crawl_peptide_urls()
        if not urls:
            log_debug("No URLs discovered during scheduled sync.", "scheduler")
            return
            
        if limit and limit > 0:
            urls = urls[:limit]
            log_debug(f"Limited scheduled sync to {limit} URLs.", "scheduler")
            
        # 2. Scrape CSV
        manager = ScraperManager()
        # Scheduled job runs till completion
        manager.run(urls, tracker=tracker)
        
        # 3. Read Data
        csv_store = CSVStorage()
        rows = csv_store.read()
        if not rows:
            log_debug("No scraped rows during scheduled sync.", "scheduler")
            return
            
        # 4. Core Sync
        db_orchestrator = DbImportOrchestrator()
        db_orchestrator.sync_to_db(db_url, rows, tracker=tracker)
        
        # 5. Graph Missing Sync
        graph_orchestrator = GraphImportOrchestrator()
        graph_orchestrator.sync_graph_missing_data(db_url, rows, tracker=tracker, action_type="scraped")
        
        log_debug("Completed scheduled combined sync successfully.", "scheduler")
        
    except Exception as e:
        log_error(f"Fatal error during scheduled combined sync: {e}", "scheduler")
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_scheduled_sync.json")
            tracker.print_summary()


def start_scheduler(interval_hours: float = 12.0, interval_minutes: float = 0.0, limit: int | None = None):
    if not scheduler.running:
        scheduler.start()
    
    # Try to add or replace the job
    scheduler.add_job(
        run_combined_sync_job,
        trigger=IntervalTrigger(hours=interval_hours, minutes=interval_minutes),
        args=[limit],
        id=SYNC_JOB_ID,
        replace_existing=True
    )
    log_debug(f"Scheduler started/updated: {interval_hours}h {interval_minutes}m interval, limit: {limit}.", "scheduler")
    

def pause_scheduler():
    try:
        scheduler.pause_job(SYNC_JOB_ID)
        log_debug("Scheduler paused.", "scheduler")
    except JobLookupError:
        pass

def resume_scheduler():
    try:
        scheduler.resume_job(SYNC_JOB_ID)
        log_debug("Scheduler resumed.", "scheduler")
    except JobLookupError:
        pass
        
def get_scheduler_status() -> dict:
    job = scheduler.get_job(SYNC_JOB_ID)
    if job:
        interval_td = getattr(job.trigger, 'interval', None)
        if interval_td:
            total_seconds = interval_td.total_seconds()
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) / 60.0
        else:
            hours = 0
            minutes = 0
            
        limit = job.args[0] if job.args else None
        next_run = job.next_run_time.isoformat() if job.next_run_time else None
        return {
            "status": "running" if job.next_run_time else "paused", 
            "interval_hours": hours, 
            "interval_minutes": minutes,
            "limit": limit,
            "next_run_time": next_run
        }
    else:
        return {"status": "not_configured"}

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
