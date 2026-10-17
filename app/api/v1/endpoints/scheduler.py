"""
Scheduler management endpoints.

The APScheduler-based background sync scheduler runs core sync operations
on a recurring interval. These endpoints let you inspect, start, pause,
and resume the scheduler independently of manual sync operations.
"""

from fastapi import APIRouter

from app.core.scheduler import (
    get_scheduler_status,
    get_vendor_scrape_scheduler_status,
    pause_scheduler,
    pause_vendor_scrape_scheduler,
    resume_scheduler,
    resume_vendor_scrape_scheduler,
    start_scheduler,
    start_vendor_scrape_scheduler,
)
from app.models.scheduler import SchedulerConfigRequest, VendorScrapeScheduleRequest

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_sync_scheduler_status():
    """
    ⏰ Get the automated sync scheduler's current status.

    Returns whether the scheduler is **running**, **paused**, or **stopped**,
    along with the configured interval and next scheduled run time.
    """
    return get_scheduler_status()


@router.post("/start")
async def start_sync_scheduler(config: SchedulerConfigRequest):
    """
    ⏰ Start or re-configure the background sync scheduler.

    The scheduler runs **core sync** (`/sync/core`) on a recurring interval.
    - Default interval: **12 hours**
    - Uses auto-discovered URLs (capped by `limit` if provided)

    ### Request Body
    - `interval_hours`: hours between runs (default 12)
    - `interval_minutes`: additional minutes (default 0)
    - `limit`: max URLs per run (`null` = unlimited)

    ### Responses
    - **200** → Scheduler started / reconfigured successfully
    - **422** → Validation error (negative interval, invalid limit)
    """
    start_scheduler(
        interval_hours=config.interval_hours,
        interval_minutes=config.interval_minutes,
        limit=config.limit,
    )
    return {
        "message": "Scheduler started/configured",
        "interval_hours": config.interval_hours,
        "interval_minutes": config.interval_minutes,
        "limit": config.limit,
    }


@router.post("/pause")
async def pause_sync_scheduler():
    """
    ⏸️ Pause the background sync scheduler.

    The scheduler job is preserved but will not fire until resumed.
    Useful during maintenance windows or manual sync operations.
    """
    pause_scheduler()
    return {"message": "Scheduler paused"}


@router.post("/resume")
async def resume_sync_scheduler():
    """
    ▶️ Resume a paused background sync scheduler.

    The scheduler will continue with its previously configured interval
    and begin counting down to the next run from the time of resumption.
    """
    resume_scheduler()
    return {"message": "Scheduler resumed"}


# ---------------------------------------------------------------------------
# Nightly competitor vendor scrape (peptides-platform#288)
# ---------------------------------------------------------------------------


@router.get("/vendor-scrape/status")
async def vendor_scrape_schedule_status():
    """
    🌙 Status of the nightly competitor price scrape.

    Cron-triggered, not interval-triggered: an interval job drifts into
    business hours, and we do not want to be loading a competitor's site at
    midday.
    """
    return get_vendor_scrape_scheduler_status()


@router.post("/vendor-scrape/start")
async def vendor_scrape_schedule_start(config: VendorScrapeScheduleRequest):
    """
    🌙 Start or re-configure the nightly competitor price scrape.

    The scheduled run and `POST /api/v1/vendors/scrape` execute the same
    pipeline with the same robots.txt, rate-limit and delta-review guards.
    """
    start_vendor_scrape_scheduler(
        hour=config.hour,
        minute=config.minute,
        vendors=config.vendors,
        limit_per_vendor=config.limit_per_vendor,
    )
    return {
        "message": "Nightly vendor scrape scheduled",
        **get_vendor_scrape_scheduler_status(),
    }


@router.post("/vendor-scrape/pause")
async def vendor_scrape_schedule_pause():
    """⏸️ Pause the nightly competitor price scrape without unscheduling it."""
    pause_vendor_scrape_scheduler()
    return {"message": "Nightly vendor scrape paused"}


@router.post("/vendor-scrape/resume")
async def vendor_scrape_schedule_resume():
    """▶️ Resume a paused nightly competitor price scrape."""
    resume_vendor_scrape_scheduler()
    return {"message": "Nightly vendor scrape resumed"}
