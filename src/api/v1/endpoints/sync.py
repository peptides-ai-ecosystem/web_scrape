from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
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
    """
    Request body for triggering a sync operation (core, graph, or graph-missing).

    - Omit `urls` (or pass `null`) to **auto-discover** peptide URLs via the crawler.
    - Provide a specific `urls` list for **targeted scraping** of known pages.
    - Use `limit` to cap the number of URLs processed (useful for testing).
    """
    limit: Optional[int] = Field(
        None,
        description="Maximum number of URLs to scrape & sync. `null` means unlimited (process all discovered or provided URLs).",
        ge=1,
        examples=[5, 10, 50],
    )
    urls: Optional[List[str]] = Field(
        None,
        description="Specific peptide page URLs to scrape. When `null` or empty, URLs are auto-discovered via the peptide URL crawler.",
        examples=[None, ["https://pep-pedia.org/peptide/1", "https://pep-pedia.org/peptide/2"]],
    )

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("limit must be a positive integer (≥1) if provided.")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"limit": 5, "urls": None},
                {"limit": 10, "urls": ["https://pep-pedia.org/peptide/1"]},
                {"limit": None, "urls": ["https://pep-pedia.org/peptide/1", "https://pep-pedia.org/peptide/2"]},
            ]
        }
    }


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
        result = orchestrator.sync_to_db(db_url, rows, tracker=tracker) or {}

        job.complete({
            "urls_scraped": len(urls),
            "rows_processed": len(rows),
            "synced_count": result.get("synced_count", 0),
            "skipped_count": result.get("skipped_count", 0),
            "synced_peptides": result.get("synced_peptides", []),
            "skipped_peptides": result.get("skipped_peptides", []),
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

        # Step 2: Scrape → writes to MASTER_CSV (overwrites previous CSV content)
        log_debug(f"Scraping {len(urls)} URL(s) and saving to CSV (will overwrite any existing CSV data)", "sync_endpoint")
        manager = ScraperManager()
        manager.run(urls, tracker=tracker, cancel_check=lambda: job.status == JobStatus.CANCELLED)
        log_debug(f"Scrape completed. CSV has been overwritten with latest scraped data", "sync_endpoint")

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

        # Step 4: Sync graph data to DB (only peptide_graph table, NOT core tables)
        log_debug(f"Starting DB injection for {len(rows)} row(s) into peptide_graph table", "sync_endpoint")
        orchestrator = GraphImportOrchestrator()
        result = orchestrator.sync_graph_data(db_url, rows, tracker=tracker, action_type="manual") or {}

        job.complete({
            "urls_scraped": len(urls),
            "rows_processed": len(rows),
            "synced_count": result.get("synced_count", 0),
            "skipped_count": result.get("skipped_count", 0),
            "synced_peptides": result.get("synced_peptides", []),
            "skipped_peptides": result.get("skipped_peptides", []),
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
        result = orchestrator.sync_graph_missing_data(db_url, rows, tracker=tracker, action_type="manual") or {}

        job.complete({
            "urls_scraped": len(urls),
            "rows_processed": len(rows),
            "synced_count": result.get("synced_count", 0),
            "skipped_count": result.get("skipped_count", 0),
            "synced_peptides": result.get("synced_peptides", []),
            "skipped_peptides": result.get("skipped_peptides", []),
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

@router.post("/core", status_code=202)
async def start_core_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    🕷️ Scrape → Sync to **core** database tables.

    Triggers a background pipeline that:

    1. **Resolves URLs** — uses provided `urls` or auto-discovers via the peptide URL crawler
    2. **Scrapes** each page with Selenium (hero, quick-guide, community, section extractors)
    3. **Writes** scraped data to the master CSV
    4. **Reads** CSV rows and syncs to **core DB tables** (peptides, benefits, side_effects,
       dosages, schedules, administration methods, interactions, indications, protocols, references)

    ### Request Body
    - `urls`: explicit list of pep-pedia URLs, or `null` for auto-discovery
    - `limit`: cap the number of URLs (useful for testing)

    ### Responses
    - **202** → Accepted. Returns a `job_id` — poll `/api/v1/operations/job/{job_id}` for status.
    - **422** → Validation error (e.g., `limit` ≤ 0, invalid types)
    - **500** → `DATABASE_URL` environment variable not configured on the server.

    ### Example
    ```json
    {"limit": 5, "urls": null}
    ```
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


@router.post("/graph", status_code=202)
async def start_graph_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    🕷️ Scrape → Sync to **graph** database tables.

    Triggers a background pipeline that:
    1. Resolves URLs (provided or auto-discovered)
    2. Scrapes each page with Selenium
    3. Syncs pharmacokinetics graph data to `peptide_graph` table

    **Only syncs graph data for peptides already present** in the core `peptides` table.

    ### Responses
    - **202** → Accepted. Returns a `job_id` for polling.
    - **422** → Validation error (invalid `limit` or `urls`).
    - **500** → `DATABASE_URL` not configured.

    ### Example
    ```json
    {"urls": ["https://pep-pedia.org/peptide/1"], "limit": null}
    ```
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


@router.post("/graph-missing", status_code=202)
async def start_graph_sync_missing(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    🕷️ Scrape → Sync **only missing** graph data.

    Same as `/graph` but **only inserts administration methods that don't yet exist**
    in the `peptide_graph` table. Idempotent — safe to run repeatedly.

    ### Use Case
    After a full graph sync, run this periodically to pick up any new administration
    methods without re-processing existing data.

    ### Responses
    - **202** → Accepted. Returns a `job_id` for polling.
    - **422** → Validation error.
    - **500** → `DATABASE_URL` not configured.

    ### Example
    ```json
    {"limit": 10, "urls": null}
    ```
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



