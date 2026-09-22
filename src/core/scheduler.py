from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError
import os

from src.utils.crawl_peptide_urls import crawl_peptide_urls
from src.services.scraper_manager import ScraperManager
from src.infrastructure.csv_storage import CSVStorage
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.mappers.graph_import_orchestrator import GraphImportOrchestrator
from src.utils.error_tracker import ErrorTracker
from pathlib import Path
from src.config import log_debug, log_error, OUTPUT_DIR, FULL_CSV

# Keep a global instance of the scheduler
scheduler = AsyncIOScheduler()
SYNC_JOB_ID = "scheduled_combined_sync"
VENDOR_SCRAPE_JOB_ID = "nightly_vendor_scrape"

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
            
        # 2. Scrape CSV (full mode — all extractors)
        manager = ScraperManager(csv_path=Path(FULL_CSV))
        # Scheduled job runs till completion
        manager.run(urls, tracker=tracker)
        
        # 3. Read Data
        csv_store = CSVStorage(csv_path=Path(FULL_CSV))
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

# ---------------------------------------------------------------------------
# Nightly competitor vendor scrape (peptides-platform#288)
# ---------------------------------------------------------------------------


def run_vendor_scrape_job(vendors: list | None = None, limit_per_vendor: int | None = None):
    """Nightly competitor price scrape.

    Runs the same pipeline as ``POST /api/v1/vendors/scrape`` — robots.txt is
    honoured, hosts are rate-limited, and sharp price moves are flagged for
    review rather than applied. A run with no configured targets is a no-op,
    not an error.
    """
    from src.services.vendor_scrape_runner import run_vendor_scrape

    try:
        log_debug("Starting nightly vendor scrape...", "scheduler")
        report = run_vendor_scrape(vendors=vendors, limit_per_vendor=limit_per_vendor)
        log_debug(
            f"Nightly vendor scrape finished: {report.get('urls_processed', 0)} URLs, "
            f"review={report.get('review_counts')}",
            "scheduler",
        )
        return report
    except Exception as e:
        log_error(f"Fatal error during nightly vendor scrape: {e}", "scheduler")
        return None


def start_vendor_scrape_scheduler(
    hour: int = 3, minute: int = 15, vendors: list | None = None, limit_per_vendor: int | None = None
):
    """Schedule the nightly vendor scrape with a cron trigger.

    Cron rather than an interval because "nightly" means *at night* — an
    interval job drifts into business hours, and hammering a competitor's
    site at midday is exactly the kind of thing we said we would not do.
    """
    if not scheduler.running:
        scheduler.start()

    scheduler.add_job(
        run_vendor_scrape_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        args=[vendors, limit_per_vendor],
        id=VENDOR_SCRAPE_JOB_ID,
        replace_existing=True,
    )
    log_debug(
        f"Nightly vendor scrape scheduled at {hour:02d}:{minute:02d} "
        f"(vendors={vendors or 'all enabled'}, limit={limit_per_vendor}).",
        "scheduler",
    )


def pause_vendor_scrape_scheduler():
    try:
        scheduler.pause_job(VENDOR_SCRAPE_JOB_ID)
        log_debug("Nightly vendor scrape paused.", "scheduler")
    except JobLookupError:
        pass


def resume_vendor_scrape_scheduler():
    try:
        scheduler.resume_job(VENDOR_SCRAPE_JOB_ID)
        log_debug("Nightly vendor scrape resumed.", "scheduler")
    except JobLookupError:
        pass


def get_vendor_scrape_scheduler_status() -> dict:
    job = scheduler.get_job(VENDOR_SCRAPE_JOB_ID)
    if not job:
        return {"status": "not_configured"}
    return {
        "status": "running" if job.next_run_time else "paused",
        "cron": str(job.trigger),
        "vendors": job.args[0] if job.args else None,
        "limit_per_vendor": job.args[1] if len(job.args) > 1 else None,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
    }


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
