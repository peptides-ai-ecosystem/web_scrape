"""Competitor vendor price scraping endpoints (peptides-platform#288, CEO round 2 P2).

HTTP only — validation, status codes, job plumbing. The pipeline itself lives
in ``src/services/vendor_scraper.py`` and its wiring in
``src/services/vendor_scrape_runner.py``.

These are what the admin "Pepti.AI -> Scrape" tab drives, through the platform
API and the orchestrator gateway (``/web_scrape/api/v1/vendors/...``):

* targets CRUD (stored in ``vendor_scrape_targets``; the targets file is the
  seed / fallback),
* run a scrape now (all targets or named ones) and poll its job,
* list observations with filters and resolve flagged ones,
* ``observations/accepted-latest`` — the one read PeptiPrices imports from.
"""
import os
from typing import Any, Dict, List, Optional

import psycopg2
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator

from src.config import (
    VENDOR_MIN_CONFIDENCE,
    VENDOR_PRICE_DELTA_THRESHOLD,
    VENDOR_SCRAPE_MIN_INTERVAL_SECONDS,
    VENDOR_SCRAPER_USER_AGENT,
    VENDOR_TARGETS_FILE,
    log_error,
    log_info,
)
from src.core.job_queue import JobStatus, get_job_queue
from src.core.vendor_models import ReviewStatus, ScrapeStatus, VendorTarget
from src.infrastructure.db.connection import DbConnection
from src.infrastructure.db.repositories import (
    VendorObservationRepository,
    VendorTargetRepository,
)
from src.infrastructure.vendor_targets import (
    VendorTargetConfigError,
    check_target_addresses,
    parse_target,
)
from src.services.vendor_scrape_runner import all_targets, run_vendor_scrape, select_targets

router = APIRouter()

SCRAPE_JOB_ENDPOINT = "/vendors/scrape"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class VendorScrapeRequest(BaseModel):
    """On-demand trigger for a competitor scrape pass."""

    vendors: Optional[List[str]] = Field(
        None,
        description="Target slugs to scrape. `null` means every **enabled** target. "
        "Unknown slugs are ignored, not guessed at.",
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


class TargetSelectors(BaseModel):
    """Ordered CSS selector candidates per field — primary first."""

    price: List[str] = Field(default_factory=list)
    stock: List[str] = Field(default_factory=list)
    coa: List[str] = Field(default_factory=list)
    product_name: List[str] = Field(default_factory=list)


class TargetPayload(BaseModel):
    """A competitor target as the admin drawer edits it."""

    slug: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$",
        description="Stable id (lowercase, digits, `-`/`_`). Immutable after create.",
    )
    name: str = Field(..., min_length=1, max_length=255)
    enabled: bool = True
    product_urls: List[str] = Field(default_factory=list, max_length=500)
    listing_url: Optional[str] = None
    listing_link_selector: Optional[str] = Field(None, max_length=500)
    selectors: TargetSelectors = Field(default_factory=TargetSelectors)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    min_request_interval_seconds: float = Field(5.0, ge=0, le=3600)
    max_products_per_run: Optional[int] = Field(None, ge=1, le=10000)
    platform_vendor_slug: Optional[str] = Field(
        None,
        max_length=255,
        description="Platform `vendors.slug` the prices are imported onto. Empty = slug.",
    )

    def to_target(self) -> VendorTarget:
        if not self.selectors.price:
            raise VendorTargetConfigError("at least one price selector is required")
        if not self.product_urls and not self.listing_url:
            raise VendorTargetConfigError("give product URLs, a listing URL, or both")
        target = parse_target(self.model_dump(), source="db")
        # SSRF: refuse hosts that resolve to internal addresses (422).
        check_target_addresses(target)
        return target


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured.")
    return db_url


def _repository() -> VendorObservationRepository:
    return VendorObservationRepository(DbConnection(_db_url()))


def _target_repository() -> VendorTargetRepository:
    return VendorTargetRepository(DbConnection(_db_url()))


def _target_view(target: VendorTarget) -> Dict[str, Any]:
    return target.to_dict()


def _running_scrape_job():
    for job in get_job_queue().list_jobs():
        if job.endpoint == SCRAPE_JOB_ENDPOINT and job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            return job
    return None


def _job_view(job) -> Dict[str, Any]:
    payload = job.to_dict()
    payload["progress_detail"] = getattr(job, "progress_detail", None)
    return payload


def _run_scrape_task(job_id: str, vendors: Optional[List[str]], limit: Optional[int]):
    """Background task wrapper around the shared runner."""
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    def on_progress(done: int, total: int) -> None:
        job.progress_detail = {"done": done, "total": total}
        job.progress = int(done * 100 / total) if total else 0

    job.start()
    log_info(f"VENDOR SCRAPE STARTED — job={job_id}, vendors={vendors or 'all enabled'}", "vendors_endpoint")
    try:
        result = run_vendor_scrape(vendors=vendors, limit_per_vendor=limit, on_progress=on_progress)
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
# Targets
# ---------------------------------------------------------------------------


@router.get("/targets")
async def list_vendor_targets() -> Dict[str, Any]:
    """🎯 List competitor targets (DB-managed, plus file fallbacks).

    `source` says where each came from: `db` (managed here, editable) or
    `file` (`VENDOR_TARGETS_FILE`, used only while no DB target has its slug;
    saving it through `PUT /targets/{slug}` takes it over into the DB).

    Also reports the exact User-Agent we send, which is deliberately honest and
    carries a contact URL, and the global politeness floor.
    """
    targets = all_targets(include_disabled=True)
    return {
        "targets_file": str(VENDOR_TARGETS_FILE),
        "user_agent": VENDOR_SCRAPER_USER_AGENT,
        "min_confidence": VENDOR_MIN_CONFIDENCE,
        "price_delta_threshold": VENDOR_PRICE_DELTA_THRESHOLD,
        "min_request_interval_floor_seconds": VENDOR_SCRAPE_MIN_INTERVAL_SECONDS,
        "count": len(targets),
        "targets": [_target_view(t) for t in targets],
    }


@router.get("/targets/{slug}", responses={404: {"description": "No such target."}})
async def get_vendor_target(slug: str) -> Dict[str, Any]:
    """One target by slug (DB first, then the file)."""
    for target in all_targets(include_disabled=True):
        if target.slug.lower() == slug.lower():
            return _target_view(target)
    raise HTTPException(status_code=404, detail=f"No vendor target '{slug}'.")


@router.post(
    "/targets",
    status_code=201,
    responses={409: {"description": "A DB target with that slug exists."}, 422: {"description": "Invalid target."}},
)
async def create_vendor_target(payload: TargetPayload) -> Dict[str, Any]:
    """➕ Add a competitor target (stored in `vendor_scrape_targets`)."""
    try:
        target = payload.to_target()
    except VendorTargetConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    repo = _target_repository()
    try:
        if repo.get(target.slug) is not None:
            raise HTTPException(status_code=409, detail=f"Vendor target '{target.slug}' already exists.")
        created = repo.create(target)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Vendor target '{target.slug}' already exists.")
    finally:
        repo.connection.close()
    return _target_view(created)


@router.put("/targets/{slug}", responses={422: {"description": "Invalid target."}})
async def update_vendor_target(slug: str, payload: TargetPayload) -> Dict[str, Any]:
    """✏️ Replace a target. A file-only target is taken over into the DB."""
    if payload.slug.lower() != slug.lower():
        raise HTTPException(status_code=422, detail="The slug cannot be changed.")
    try:
        target = payload.to_target()
    except VendorTargetConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    repo = _target_repository()
    try:
        updated = repo.update(slug, target)
        if updated is None:
            updated = repo.create(target)
    finally:
        repo.connection.close()
    return _target_view(updated)


@router.delete(
    "/targets/{slug}",
    status_code=204,
    responses={404: {"description": "No DB target."}, 409: {"description": "Target lives in the file."}},
)
async def delete_vendor_target(slug: str) -> Response:
    """🗑️ Remove a DB target. Observations already stored are kept (audit trail)."""
    repo = _target_repository()
    try:
        deleted = repo.delete(slug)
    finally:
        repo.connection.close()
    if not deleted:
        in_file = any(t.slug.lower() == slug.lower() for t in all_targets(include_disabled=True))
        if in_file:
            raise HTTPException(
                status_code=409,
                detail=f"'{slug}' is defined in VENDOR_TARGETS_FILE; save it disabled to pause it.",
            )
        raise HTTPException(status_code=404, detail=f"No vendor target '{slug}'.")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Scrape runs
# ---------------------------------------------------------------------------


@router.post(
    "/scrape",
    responses={
        202: {"description": "Scrape accepted; poll /vendors/scrape/jobs/{job_id}."},
        400: {"description": "No enabled targets match the request."},
        409: {"description": "A scrape is already running."},
    },
    status_code=202,
)
async def trigger_vendor_scrape(
    request: VendorScrapeRequest, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """🕷️ Trigger a competitor price scrape now (all enabled targets, or named ones).

    Runs the identical pipeline the nightly cron runs — robots.txt is checked
    before each fetch, requests are rate-limited per host, and readings that
    move a price sharply are flagged rather than applied. One run at a time:
    two concurrent runs would double the request rate against the same hosts.

    Returns **202** with a `job_id`; poll `/api/v1/vendors/scrape/jobs/{job_id}`.
    """
    running = _running_scrape_job()
    if running is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A vendor scrape is already running (job {running.job_id}).",
        )

    targets = select_targets(request.vendors)
    if not targets:
        raise HTTPException(
            status_code=400,
            detail="No enabled vendor targets match this request. Add or enable one first.",
        )

    queue = get_job_queue()
    job = queue.create_job(
        SCRAPE_JOB_ENDPOINT,
        {
            "vendors": [t.slug for t in targets],
            "limit_per_vendor": request.limit_per_vendor,
        },
    )
    job.progress_detail = {"done": 0, "total": None}
    background_tasks.add_task(
        _run_scrape_task, job.job_id, [t.slug for t in targets], request.limit_per_vendor
    )
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "vendors": [t.slug for t in targets],
        "message": "Vendor scrape started. Poll /api/v1/vendors/scrape/jobs/{job_id}.",
    }


@router.get("/scrape/jobs")
async def list_vendor_scrape_jobs(
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    """Recent vendor scrape jobs, newest first (in-memory; cleared on restart)."""
    jobs = [j for j in get_job_queue().list_jobs() if j.endpoint == SCRAPE_JOB_ENDPOINT]
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    views = []
    for job in jobs[:limit]:
        view = _job_view(job)
        # The list is a summary; the full per-URL report stays on the job read.
        if isinstance(view.get("result"), dict):
            view["result"] = {k: v for k, v in view["result"].items() if k != "observations"}
        views.append(view)
    return {"count": len(views), "jobs": views}


@router.get("/scrape/jobs/{job_id}", responses={404: {"description": "Unknown job."}})
async def get_vendor_scrape_job(job_id: str) -> Dict[str, Any]:
    """Status of one scrape: `progress` (0-100), `progress_detail` {done,total}, result."""
    job = get_job_queue().get_job(job_id)
    if job is None or job.endpoint != SCRAPE_JOB_ENDPOINT:
        raise HTTPException(status_code=404, detail=f"No vendor scrape job '{job_id}'.")
    return _job_view(job)


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------


_REVIEW_VALUES = {s.value for s in ReviewStatus}
_STATUS_VALUES = {s.value for s in ScrapeStatus}


@router.get("/observations")
async def list_observations(
    vendor: Optional[str] = Query(None, description="Restrict to one vendor slug."),
    review_status: Optional[str] = Query(None, description="accepted | flagged | rejected"),
    status: Optional[str] = Query(None, description="ok | robots_disallowed | blocked | error | skipped"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """📋 Every reading, newest first, filterable by vendor / review status / scrape status."""
    if review_status and review_status not in _REVIEW_VALUES:
        raise HTTPException(status_code=422, detail=f"review_status must be one of {sorted(_REVIEW_VALUES)}")
    if status and status not in _STATUS_VALUES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_STATUS_VALUES)}")
    repo = _repository()
    try:
        page = repo.list_observations(
            vendor=vendor, review_status=review_status, status=status, limit=limit, offset=offset
        )
    finally:
        repo.connection.close()
    return {
        "total": page["total"],
        "limit": limit,
        "offset": offset,
        "observations": page["rows"],
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
    try:
        rows = repo.list_flagged(limit=limit, vendor=vendor)
    finally:
        repo.connection.close()
    return {"count": len(rows), "vendor": vendor, "observations": rows}


@router.get("/observations/accepted-latest")
async def list_latest_accepted_observations(
    vendor: Optional[str] = Query(None, description="Restrict to one vendor slug."),
) -> Dict[str, Any]:
    """✅ The current accepted reading per listing — what PeptiPrices imports.

    One row per `(vendor, url)`: the newest **accepted** observation with a
    price. Flagged and rejected readings never appear here. Each row carries
    the target's `platform_vendor_slug` (the platform `vendors.slug` it maps
    to; the vendor slug itself when unset) so the importer needs no second call.
    """
    repo = _repository()
    try:
        rows = repo.list_latest_accepted(vendor=vendor)
    finally:
        repo.connection.close()
    mapping = {t.slug.lower(): t for t in all_targets(include_disabled=True)}
    for row in rows:
        target = mapping.get(str(row.get("vendor") or "").lower())
        row["vendor_name"] = target.name if target else None
        row["platform_vendor_slug"] = (
            (target.platform_vendor_slug or target.slug) if target else row.get("vendor")
        )
    return {"count": len(rows), "vendor": vendor, "observations": rows}


@router.post(
    "/observations/{observation_id}/review",
    responses={
        200: {"description": "Review recorded."},
        404: {"description": "No such observation."},
        409: {"description": "Already resolved, or accepting a reading with no price."},
    },
)
async def review_observation(observation_id: int, request: ReviewRequest) -> Dict[str, Any]:
    """✅ Resolve one flagged observation.

    `accept` makes this reading the current value for its listing; `reject`
    leaves the previously accepted value in place. Only a **flagged** row can
    be resolved, so a review can never quietly un-accept a value other things
    are already reading — and only a reading with a price can be accepted.
    """
    repo = _repository()
    try:
        status = ReviewStatus.ACCEPTED if request.decision == "accept" else ReviewStatus.REJECTED
        updated = repo.resolve_review(observation_id, status, request.reviewer)
        if not updated:
            row = repo.get_row(observation_id)
            if row is None:
                raise HTTPException(status_code=404, detail=f"No observation {observation_id}.")
            if row.get("review_status") != ReviewStatus.FLAGGED.value:
                raise HTTPException(
                    status_code=409,
                    detail=f"Observation {observation_id} is already {row.get('review_status')}.",
                )
            raise HTTPException(
                status_code=409,
                detail=f"Observation {observation_id} has no price and can only be rejected.",
            )
    finally:
        repo.connection.close()
    return {"observation_id": observation_id, "review_status": status.value, "updated": updated}
