"""Competitor vendor price scraping endpoints (peptides-platform#288).

HTTP only — validation, status codes, job plumbing. The pipeline itself lives
in ``src/services/vendor_scraper.py`` and its wiring in
``src/services/vendor_scrape_runner.py``.
"""
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src.config import (
    VENDOR_MIN_CONFIDENCE,
    VENDOR_PRICE_DELTA_THRESHOLD,
    VENDOR_SCRAPER_USER_AGENT,
    VENDOR_TARGETS_FILE,
    log_error,
    log_info,
)
from src.core.job_queue import get_job_queue
from src.core.vendor_models import ReviewStatus
from src.infrastructure.db.connection import DbConnection
from src.infrastructure.db.repositories import VendorObservationRepository
from src.services.vendor_scrape_runner import run_vendor_scrape, select_targets

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class VendorScrapeRequest(BaseModel):
    """On-demand trigger for a competitor scrape pass."""

    vendors: Optional[List[str]] = Field(
        None,
        description="Target slugs to scrape. `null` means every **enabled** target "
        "in the configured targets file. Unknown slugs are ignored, not guessed at.",
        examples=[None, ["competitor-a"]],
    )
    limit_per_vendor: Optional[int] = Field(
        None,
        description="Cap on product URLs fetched per vendor this run. `null` means "
        "the vendor's own `max_products_per_run`, or all of them.",
        ge=1,
        examples=[None, 5],
    )

    @field_validator("vendors")
    @classmethod
    def validate_vendors(cls, v):
        if v is None:
            return v
        cleaned = [s.strip() for s in v if isinstance(s, str) and s.strip()]
        if not cleaned:
            raise ValueError("vendors must be a list of non-empty slugs, or null.")
        return cleaned


class ReviewRequest(BaseModel):
    """A human's verdict on a flagged observation."""

    decision: str = Field(
        ...,
        description="`accept` promotes the reading to the current value; "
        "`reject` discards it and leaves the previously accepted value standing.",
        examples=["accept", "reject"],
    )
    reviewer: Optional[str] = Field(
        None, description="Who reviewed it — recorded for the audit trail.", max_length=255
    )

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v):
        normalised = (v or "").strip().lower()
        if normalised not in {"accept", "reject"}:
            raise ValueError("decision must be 'accept' or 'reject'.")
        return normalised


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repository() -> VendorObservationRepository:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured.")
    return VendorObservationRepository(DbConnection(db_url))


def _run_scrape_task(job_id: str, vendors: Optional[List[str]], limit: Optional[int]):
    """Background task wrapper around the shared runner."""
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    log_info(f"VENDOR SCRAPE STARTED — job={job_id}, vendors={vendors or 'all enabled'}", "vendors_endpoint")
    try:
        result = run_vendor_scrape(vendors=vendors, limit_per_vendor=limit)
        job.progress = 100
        job.complete(result)
        log_info(
            f"VENDOR SCRAPE FINISHED — job={job_id}, "
            f"urls={result.get('urls_processed')}, review={result.get('review_counts')}",
            "vendors_endpoint",
        )
    except Exception as exc:  # noqa: BLE001
        log_error(f"Vendor scrape job {job_id} failed: {exc}", "vendors_endpoint")
        job.fail(str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/targets")
async def list_vendor_targets() -> Dict[str, Any]:
    """🎯 List the configured competitor targets.

    Targets are configuration, not code: edit the file named by
    `VENDOR_TARGETS_FILE` to add, pause (`"enabled": false`) or remove a site.
    No deploy is needed and nothing is hardcoded, so a site can always be
    dropped.

    Also reports the exact User-Agent we send, which is deliberately honest and
    carries a contact URL.
    """
    targets = select_targets(include_disabled=True)
    return {
        "targets_file": str(VENDOR_TARGETS_FILE),
        "user_agent": VENDOR_SCRAPER_USER_AGENT,
        "min_confidence": VENDOR_MIN_CONFIDENCE,
        "price_delta_threshold": VENDOR_PRICE_DELTA_THRESHOLD,
        "count": len(targets),
        "targets": [
            {
                "slug": t.slug,
                "name": t.name,
                "enabled": t.enabled,
                "product_urls": list(t.product_urls),
                "currency": t.currency,
                "min_request_interval_seconds": t.min_request_interval_seconds,
                "max_products_per_run": t.max_products_per_run,
                "selectors": {
                    "price": list(t.selectors.price),
                    "stock": list(t.selectors.stock),
                    "coa": list(t.selectors.coa),
                    "product_name": list(t.selectors.product_name),
                },
            }
            for t in targets
        ],
    }


@router.post(
    "/scrape",
    responses={
        202: {"description": "Scrape accepted; poll /operations/job/{job_id}."},
        400: {"description": "No enabled targets match the request."},
    },
    status_code=202,
)
async def trigger_vendor_scrape(
    request: VendorScrapeRequest, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """🕷️ Trigger a competitor price scrape now.

    Runs the identical pipeline the nightly cron runs — robots.txt is checked
    before each fetch, requests are rate-limited per host, and readings that
    move a price sharply are flagged rather than applied.

    Returns **202** with a `job_id`; poll `/api/v1/operations/job/{job_id}`.
    """
    targets = select_targets(request.vendors)
    if not targets:
        raise HTTPException(
            status_code=400,
            detail=(
                "No enabled vendor targets match this request. Check "
                f"VENDOR_TARGETS_FILE ({VENDOR_TARGETS_FILE}) and the 'enabled' flags."
            ),
        )

    queue = get_job_queue()
    job = queue.create_job(
        "/vendors/scrape",
        {
            "vendors": [t.slug for t in targets],
            "limit_per_vendor": request.limit_per_vendor,
        },
    )
    background_tasks.add_task(
        _run_scrape_task, job.job_id, [t.slug for t in targets], request.limit_per_vendor
    )
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "vendors": [t.slug for t in targets],
        "message": "Vendor scrape started. Poll /api/v1/operations/job/{job_id}.",
    }


@router.get("/observations/flagged")
async def list_flagged_observations(
    limit: int = Query(50, ge=1, le=500, description="Maximum rows to return."),
    vendor: Optional[str] = Query(None, description="Restrict to one vendor slug."),
) -> Dict[str, Any]:
    """🚩 The review queue.

    Every reading the scraper did not trust enough to stand on its own: a
    price that moved more than the delta threshold, a low-confidence
    extraction, a page with no readable price, a blocked host. None of these
    has replaced a previously accepted value.
    """
    repo = _repository()
    rows = repo.list_flagged(limit=limit, vendor=vendor)
    return {"count": len(rows), "vendor": vendor, "observations": rows}


@router.post(
    "/observations/{observation_id}/review",
    responses={
        200: {"description": "Review recorded."},
        404: {"description": "No flagged observation with that id."},
    },
)
async def review_observation(observation_id: int, request: ReviewRequest) -> Dict[str, Any]:
    """✅ Resolve one flagged observation.

    `accept` makes this reading the current value for its listing; `reject`
    leaves the previously accepted value in place. Only a **flagged** row can
    be resolved, so a review can never quietly un-accept a value other things
    are already reading.
    """
    repo = _repository()
    status = ReviewStatus.ACCEPTED if request.decision == "accept" else ReviewStatus.REJECTED
    updated = repo.resolve_review(observation_id, status, request.reviewer)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"No flagged observation {observation_id} to review (already resolved?).",
        )
    return {"observation_id": observation_id, "review_status": status.value, "updated": updated}
