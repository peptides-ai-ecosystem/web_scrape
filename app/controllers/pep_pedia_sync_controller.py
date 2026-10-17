"""pep-pedia sync use case: resolve URLs -> scrape -> CSV -> mappers -> platform tables.

``POST /api/v1/sync/{core,graph,graph-missing}`` create a job and hand one of
the ``run_*_task`` functions below to ``schedule`` (the endpoint passes
``BackgroundTasks.add_task``). Each task coordinates the scraper
(``ScraperManager``), the CSV store and a mapper orchestrator, so this is a
controller rather than a service. The scheduled combined sync
(``app/core/scheduler.py``) runs the same pieces on an interval.
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.config import ENHANCED_CSV, GRAPH_CSV, OUTPUT_DIR
from app.core.errors import ConfigurationError
from app.core.job_queue import JobStatus, get_job_queue
from app.core.logging import log_debug, log_error, log_info, log_success
from app.core.models import ScrapeMode
from app.infrastructure.csv_storage import CSVStorage
from app.models.sync import SyncRequest
from app.scrapers.pep_pedia.crawl_peptide_urls import crawl_peptide_urls
from app.scrapers.pep_pedia.scraper_manager import ScraperManager
from app.services.sync.db_import_orchestrator import DbImportOrchestrator
from app.services.sync.graph_import_orchestrator import GraphImportOrchestrator
from app.utils.error_tracker import ErrorTracker

Schedule = Callable[..., Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_urls(requested_urls: list[str] | None, limit: int | None) -> list[str]:
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


def run_core_sync_task(
    job_id: str, requested_urls: list[str] | None, limit: int | None, db_url: str, fill_empty_only: bool = False
):
    """
    Background task: discover/resolve URLs → scrape → sync to core DB tables.
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    tracker = ErrorTracker()

    log_info(
        f"CORE PIPELINE STARTED — job={job_id}, limit={limit}, urls_provided={len(requested_urls) if requested_urls else 'auto'}",
        "sync_endpoint",
    )

    try:
        # Step 1: Resolve URLs
        urls = _resolve_urls(requested_urls, limit)
        if not urls:
            log_error("No URLs discovered or provided. Sync aborted.", "sync_endpoint")
            job.fail("No URLs discovered or provided. Sync aborted.")
            return

        log_info(f"Core sync — scraping {len(urls)} URLs", "sync_endpoint")

        # Step 2: Scrape → writes to ENHANCED_CSV (core-only: skip graph extractor)
        log_debug(f"Core sync: scraping with mode=CORE_ONLY to {ENHANCED_CSV}", "sync_endpoint")
        manager = ScraperManager(csv_path=Path(ENHANCED_CSV))
        manager.run(
            urls,
            tracker=tracker,
            cancel_check=lambda: job.status == JobStatus.CANCELLED,
            scrape_mode=ScrapeMode.CORE_ONLY,
        )

        if job.status == JobStatus.CANCELLED:
            log_debug("Job cancelled during scraping. Aborting DB sync.", "sync_endpoint")
            return

        # Step 3: Read scraped data from CSV
        csv_store = CSVStorage(csv_path=Path(ENHANCED_CSV))
        rows = csv_store.read()

        if not rows:
            log_debug("Scrape produced no rows. Completing with 0 rows synced.", "sync_endpoint")
            job.complete(
                {
                    "urls_scraped": len(urls),
                    "rows_synced": 0,
                    "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                    "db_errors": 0,
                }
            )
            return

        # Step 4: Sync to core DB tables
        orchestrator = DbImportOrchestrator()
        result = (
            orchestrator.sync_to_db(
                db_url, rows, tracker=tracker, activity_type="manual", fill_empty_only=fill_empty_only
            )
            or {}
        )

        job.complete(
            {
                "urls_scraped": len(urls),
                "rows_processed": len(rows),
                "synced_count": result.get("synced_count", 0),
                "skipped_count": result.get("skipped_count", 0),
                "synced_peptides": result.get("synced_peptides", []),
                "skipped_peptides": result.get("skipped_peptides", []),
                "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                "db_errors": len(tracker.db_errors) if tracker.has_errors() else 0,
            }
        )

        log_success(
            f"CORE PIPELINE COMPLETED — job={job_id} | {result.get('synced_count', 0)} synced, {result.get('skipped_count', 0)} skipped, {len(tracker.scrape_errors) if tracker.has_errors() else 0} scrape errors",
            "sync_endpoint",
        )

    except Exception as e:
        log_error(f"CORE PIPELINE FAILED — job={job_id}: {e}", "sync_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_core_sync.json")
            tracker.print_summary()


# ---------------------------------------------------------------------------
# Graph Sync (Scrape → Graph DB Tables)
# ---------------------------------------------------------------------------


def run_graph_sync_task(
    job_id: str, requested_urls: list[str] | None, limit: int | None, db_url: str, fill_empty_only: bool = False
):
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

    log_info(
        f"GRAPH PIPELINE STARTED — job={job_id}, limit={limit}, urls_provided={len(requested_urls) if requested_urls else 'auto'}",
        "sync_endpoint",
    )

    try:
        # Step 1: Resolve URLs
        urls = _resolve_urls(requested_urls, limit)
        if not urls:
            log_error("No URLs discovered or provided. Sync aborted.", "sync_endpoint")
            job.fail("No URLs discovered or provided. Sync aborted.")
            return

        log_info(f"Graph sync — scraping {len(urls)} URLs", "sync_endpoint")

        # Step 2: Scrape → writes to GRAPH_CSV (graph-only fields)
        log_debug(f"Graph sync: scraping {len(urls)} URL(s) to {GRAPH_CSV}", "sync_endpoint")
        manager = ScraperManager(csv_path=Path(GRAPH_CSV))
        manager.run(
            urls,
            tracker=tracker,
            cancel_check=lambda: job.status == JobStatus.CANCELLED,
            scrape_mode=ScrapeMode.GRAPH_ONLY,
        )
        log_debug(f"Scrape completed. Graph data saved to {GRAPH_CSV}", "sync_endpoint")

        if job.status == JobStatus.CANCELLED:
            log_debug("Job cancelled during scraping. Aborting DB sync.", "sync_endpoint")
            return

        # Step 3: Read scraped data from CSV
        csv_store = CSVStorage(csv_path=Path(GRAPH_CSV))
        rows = csv_store.read()

        if not rows:
            log_debug("Scrape produced no rows. Completing with 0 rows processed.", "sync_endpoint")
            job.complete(
                {
                    "urls_scraped": len(urls),
                    "rows_processed": 0,
                    "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                    "db_errors": 0,
                }
            )
            return

        # Step 4: Sync graph data to DB (only peptide_graph table, NOT core tables)
        log_debug(f"Starting DB injection for {len(rows)} row(s) into peptide_graph table", "sync_endpoint")
        orchestrator = GraphImportOrchestrator()
        result = (
            orchestrator.sync_graph_data(
                db_url, rows, tracker=tracker, action_type="manual", fill_empty_only=fill_empty_only
            )
            or {}
        )

        job.complete(
            {
                "urls_scraped": len(urls),
                "rows_processed": len(rows),
                "synced_count": result.get("synced_count", 0),
                "skipped_count": result.get("skipped_count", 0),
                "synced_peptides": result.get("synced_peptides", []),
                "skipped_peptides": result.get("skipped_peptides", []),
                "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                "db_errors": len(tracker.db_errors) if tracker.has_errors() else 0,
            }
        )

        log_success(
            f"GRAPH PIPELINE COMPLETED — job={job_id} | {result.get('synced_count', 0)} synced, {result.get('skipped_count', 0)} skipped",
            "sync_endpoint",
        )

    except Exception as e:
        log_error(f"GRAPH PIPELINE FAILED — job={job_id}: {e}", "sync_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_graph_sync.json")
            tracker.print_summary()


def run_graph_sync_missing_task(job_id: str, requested_urls: list[str] | None, limit: int | None, db_url: str):
    """
    Background task: discover/resolve URLs → scrape → sync to graph DB tables (only if missing).
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    tracker = ErrorTracker()

    log_info(
        f"GRAPH MISSING PIPELINE STARTED — job={job_id}, limit={limit}, urls_provided={len(requested_urls) if requested_urls else 'auto'}",
        "sync_endpoint",
    )

    try:
        # Step 1: Resolve URLs
        urls = _resolve_urls(requested_urls, limit)
        if not urls:
            log_error("No URLs discovered or provided. Sync aborted.", "sync_endpoint")
            job.fail("No URLs discovered or provided. Sync aborted.")
            return

        log_info(f"Graph missing sync — scraping {len(urls)} URLs", "sync_endpoint")

        # Step 2: Scrape → writes to GRAPH_CSV (graph-only fields)
        manager = ScraperManager(csv_path=Path(GRAPH_CSV))
        manager.run(
            urls,
            tracker=tracker,
            cancel_check=lambda: job.status == JobStatus.CANCELLED,
            scrape_mode=ScrapeMode.GRAPH_ONLY,
        )

        if job.status == JobStatus.CANCELLED:
            log_debug("Job cancelled during scraping. Aborting DB sync.", "sync_endpoint")
            return

        # Step 3: Read scraped data from CSV
        csv_store = CSVStorage(csv_path=Path(GRAPH_CSV))
        rows = csv_store.read()

        if not rows:
            log_debug("Scrape produced no rows. Completing with 0 rows processed.", "sync_endpoint")
            job.complete(
                {
                    "urls_scraped": len(urls),
                    "rows_processed": 0,
                    "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                    "db_errors": 0,
                }
            )
            return

        # Step 4: Sync to graph DB tables
        orchestrator = GraphImportOrchestrator()
        result = orchestrator.sync_graph_missing_data(db_url, rows, tracker=tracker, action_type="manual") or {}

        job.complete(
            {
                "urls_scraped": len(urls),
                "rows_processed": len(rows),
                "synced_count": result.get("synced_count", 0),
                "skipped_count": result.get("skipped_count", 0),
                "synced_peptides": result.get("synced_peptides", []),
                "skipped_peptides": result.get("skipped_peptides", []),
                "scrape_errors": len(tracker.scrape_errors) if tracker.has_errors() else 0,
                "db_errors": len(tracker.db_errors) if tracker.has_errors() else 0,
            }
        )

        log_success(
            f"GRAPH MISSING PIPELINE COMPLETED — job={job_id} | {result.get('synced_count', 0)} synced, {result.get('skipped_count', 0)} skipped",
            "sync_endpoint",
        )

    except Exception as e:
        log_error(f"GRAPH MISSING PIPELINE FAILED — job={job_id}: {e}", "sync_endpoint")
        job.fail(str(e))
    finally:
        if tracker.has_errors():
            tracker.save(OUTPUT_DIR / "tracker_report_graph_missing_sync.json")
            tracker.print_summary()


# ---------------------------------------------------------------------------
# Use cases (one per route)
# ---------------------------------------------------------------------------


def _db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ConfigurationError("DATABASE_URL not configured.")
    return db_url


class PepPediaSyncController:
    """Starts the three pep-pedia sync jobs. ``schedule(fn, *args, **kwargs)`` runs ``fn`` after the response."""

    def __init__(self, schedule: Schedule):
        self._schedule = schedule

    def start_core(self, request: SyncRequest) -> dict[str, Any]:
        db_url = _db_url()
        queue = get_job_queue()
        job = queue.create_job(
            "/sync/core",
            {
                "limit": request.limit,
                "urls_provided": len(request.urls) if request.urls else 0,
                "mode": "targeted" if request.urls else "auto-discover",
                "fill_empty_only": request.fill_empty_only,
            },
        )
        self._schedule(
            run_core_sync_task, job.job_id, request.urls, request.limit, db_url, fill_empty_only=request.fill_empty_only
        )
        return job.to_dict()

    def start_graph(self, request: SyncRequest) -> dict[str, Any]:
        db_url = _db_url()
        queue = get_job_queue()
        job = queue.create_job(
            "/sync/graph",
            {
                "limit": request.limit,
                "urls_provided": len(request.urls) if request.urls else 0,
                "mode": "targeted" if request.urls else "auto-discover",
                "fill_empty_only": request.fill_empty_only,
            },
        )
        self._schedule(
            run_graph_sync_task,
            job.job_id,
            request.urls,
            request.limit,
            db_url,
            fill_empty_only=request.fill_empty_only,
        )
        return job.to_dict()

    def start_graph_missing(self, request: SyncRequest) -> dict[str, Any]:
        db_url = _db_url()
        queue = get_job_queue()
        job = queue.create_job(
            "/sync/graph-missing",
            {
                "limit": request.limit,
                "urls_provided": len(request.urls) if request.urls else 0,
                "mode": "targeted" if request.urls else "auto-discover",
            },
        )
        self._schedule(run_graph_sync_missing_task, job.job_id, request.urls, request.limit, db_url)
        return job.to_dict()
