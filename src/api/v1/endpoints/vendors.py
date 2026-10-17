"""Competitor vendor price scraping endpoints (peptides-platform#288, CEO round 2 P2).

HTTP only — validation, status codes, job plumbing. The pipeline itself lives
in ``src/services/vendor_scraper.py`` and its wiring in
``src/services/vendor_scrape_runner.py``.

These are what the admin "Pepti.AI -> Scrape" tab drives, through the platform
API and the orchestrator gateway (``/web_scrape/api/v1/vendors/...``):

* targets CRUD (stored in ``vendor_scrape_targets``; the targets file is the
  seed / fallback), paginated with ``limit``/``offset``,
* URL-only targets (AAD-1): ``POST /targets/from-url`` creates a draft
  competitor target from a bare store URL, ``POST /targets/{slug}/approve``
  lets runs read it, ``POST /discover`` previews what a URL yields,
* run a scrape now (all targets or named ones) and poll its job,
* list observations with filters and resolve flagged ones,
* ``observations/accepted-latest`` — the one read PeptiPrices imports from.
"""
import os
import re
from typing import Annotated, Any, Dict, List, Optional
from urllib.parse import urlsplit

import psycopg2
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool
from src.models.vendors import (
    ApproveRequest,
    DiscoverRequest,
    FromUrlRequest,
    ReviewRequest,
    TargetPayload,
    VendorScrapeRequest,
)

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
from src.core.sentry import capture_background_failure
from src.core.owned_stores import owned_reason
from src.core.vendor_models import (
    DiscoveryMode,
    ReviewStatus,
    ScrapeStatus,
    TargetReviewState,
    VendorTarget,
)
from src.infrastructure.db.connection import DbConnection
from src.infrastructure.db.repositories import (
    VendorObservationRepository,
    VendorTargetRepository,
)
from src.infrastructure.url_safety import UnsafeTargetURLError, check_url
from src.infrastructure.vendor_targets import (
    VendorTargetConfigError,
    check_not_owned,
    check_target_addresses,
    parse_target,
    target_urls,
)
from src.services.vendor_scrape_runner import (
    all_targets,
    preview_discovery,
    run_vendor_scrape,
    select_targets,
)

router = APIRouter()

SCRAPE_JOB_ENDPOINT = "/vendors/scrape"


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


def slug_from_url(url: str) -> str:
    """``https://www.glpeptides.is/shop`` -> ``glpeptides-is``."""
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    slug = re.sub(r"[^a-z0-9]+", "-", host).strip("-")[:64].strip("-")
    return slug or "competitor"


def _check_public_url(url: str) -> None:
    """422 for anything that is not a public http(s) URL or is our own store."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise HTTPException(status_code=422, detail=f"'{url}' is not an absolute http(s) URL.")
    owned = owned_reason([url])
    if owned:
        raise HTTPException(status_code=422, detail=owned)
    try:
        check_url(url)
    except UnsafeTargetURLError as exc:
        raise HTTPException(status_code=422, detail=f"'{url}' is not allowed: {exc}")


def _matches(target: VendorTarget, q: str) -> bool:
    needle = q.strip().lower()
    haystack = [target.slug, target.name, target.platform_vendor_slug or ""] + target_urls(target)
    return any(needle in (h or "").lower() for h in haystack)


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
        # FEEDBACK-3 G15: the run failed as a whole — one Sentry event under
        # its own trace_id (the 202 has already been sent).
        trace_id = capture_background_failure(exc, job="vendor_scrape", job_id=job_id)
        log_error(f"Vendor scrape job {job_id} failed (trace_id={trace_id}): {exc}", "vendors_endpoint")
        job.fail(str(exc))


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


_TARGET_STATES = {s.value for s in TargetReviewState}
_TARGET_MODES = {m.value for m in DiscoveryMode}


@router.get("/targets")
async def list_vendor_targets(
    limit: Annotated[
        Optional[int],
        Query(ge=1, le=500, description="Page size. Omitted = every target (the original behaviour)."),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[
        Optional[str], Query(max_length=255, description="Search slug, name, platform slug and URLs.")
    ] = None,
    review_state: Annotated[Optional[str], Query(description="draft | approved")] = None,
    discovery_mode: Annotated[Optional[str], Query(description="selectors | auto")] = None,
) -> Dict[str, Any]:
    """🎯 List competitor targets (DB-managed, plus file fallbacks).

    `source` says where each came from: `db` (managed here, editable) or
    `file` (`VENDOR_TARGETS_FILE`, used only while no DB target has its slug;
    saving it through `PUT /targets/{slug}` takes it over into the DB).

    Paginated (AAD-1): `total` is the number matching the filters, `count`
    the number on this page. Without `limit` every target is returned, as
    before. `review_state=draft` lists URL-only targets awaiting approval.

    Also reports the exact User-Agent we send, which is deliberately honest and
    carries a contact URL, and the global politeness floor.
    """
    if review_state and review_state not in _TARGET_STATES:
        raise HTTPException(status_code=422, detail=f"review_state must be one of {sorted(_TARGET_STATES)}")
    if discovery_mode and discovery_mode not in _TARGET_MODES:
        raise HTTPException(status_code=422, detail=f"discovery_mode must be one of {sorted(_TARGET_MODES)}")
    everything = all_targets(include_disabled=True)
    targets = list(everything)
    if review_state:
        targets = [t for t in targets if t.review_state.value == review_state]
    if discovery_mode:
        targets = [t for t in targets if t.discovery_mode.value == discovery_mode]
    if q and q.strip():
        targets = [t for t in targets if _matches(t, q)]
    total = len(targets)
    page = targets[offset: offset + limit] if limit is not None else targets[offset:]
    return {
        "targets_file": str(VENDOR_TARGETS_FILE),
        "user_agent": VENDOR_SCRAPER_USER_AGENT,
        "min_confidence": VENDOR_MIN_CONFIDENCE,
        "price_delta_threshold": VENDOR_PRICE_DELTA_THRESHOLD,
        "min_request_interval_floor_seconds": VENDOR_SCRAPE_MIN_INTERVAL_SECONDS,
        "count": len(page),
        "total": total,
        "limit": limit,
        "offset": offset,
        # Across every target, whatever the filters: the tab's "awaiting approval" badge.
        "draft_count": sum(1 for t in everything if not t.is_approved),
        "targets": [_target_view(t) for t in page],
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
    """➕ Add a competitor target (stored in `vendor_scrape_targets`).

    With a price selector it is approved at once, as before. Without one it is
    a selector-free (URL-only) target and starts as a **draft**: no run reads
    it until `POST /targets/{slug}/approve`. Our own stores are refused (422).
    """
    try:
        auto = not payload.selectors.price
        target = payload.to_target(
            review_state=(TargetReviewState.DRAFT if auto else TargetReviewState.APPROVED).value
        )
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
    repo = _target_repository()
    try:
        # review_state is not editable here: keep what the row has. A file
        # target taken over keeps "approved" (file targets always were).
        existing = repo.get(slug)
        state: Dict[str, Any] = {}
        if existing is not None:
            state = {
                "review_state": existing.review_state.value,
                "approved_at": existing.approved_at,
                "approved_by": existing.approved_by,
            }
            if "store_url" not in payload.model_fields_set:
                # A client that predates store_url (the admin drawer today)
                # must not wipe it by saving the target.
                state["store_url"] = existing.store_url
        elif not payload.selectors.price and not any(
            t.slug.lower() == slug.lower() for t in all_targets(include_disabled=True)
        ):
            # A brand-new selector-free target is a draft, however it is created.
            state = {"review_state": TargetReviewState.DRAFT.value}
        try:
            target = payload.to_target(**state)
        except VendorTargetConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
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


@router.post(
    "/targets/from-url",
    status_code=201,
    responses={
        409: {"description": "A target with that slug exists."},
        422: {"description": "Not a public http(s) URL, or one of our own stores."},
    },
)
async def create_target_from_url(payload: FromUrlRequest) -> Dict[str, Any]:
    """🔗 AAD-1: a competitor target from a URL only — no selectors.

    Give a store's home, shop or product URL. The target is created as a
    **draft** competitor target (`review_state: draft`, `discovery_mode:
    auto`): it shows in the Scrape tab and can be previewed with
    `POST /discover`, but no scrape run reads it until an admin calls
    `POST /targets/{slug}/approve`. Our own stores (arcane, ruo, bulk,
    moglabs) are refused with 422 — competitor and own vendors stay separate.

    A home/shop URL is read through the WooCommerce Store API, Shopify
    `products.json` or the sitemap; a product URL reads just that product.
    Selectors can still be added later with `PUT /targets/{slug}`.
    """
    url = payload.url.strip()
    _check_public_url(url)
    slug = payload.slug or slug_from_url(url)
    body = {
        "slug": slug,
        "name": payload.name or (urlsplit(url).hostname or slug).removeprefix("www."),
        "enabled": True,
        "store_url": url,
        "currency": payload.currency,
        "platform_vendor_slug": payload.platform_vendor_slug,
        "max_products_per_run": payload.max_products_per_run,
        "review_state": TargetReviewState.DRAFT.value,
    }
    try:
        target = parse_target(body, source="db")
        check_not_owned(target)
        check_target_addresses(target)
    except VendorTargetConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if any(t.slug.lower() == slug.lower() for t in all_targets(include_disabled=True)):
        raise HTTPException(status_code=409, detail=f"Vendor target '{slug}' already exists.")
    repo = _target_repository()
    try:
        created = repo.create(target)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Vendor target '{slug}' already exists.")
    finally:
        repo.connection.close()
    log_info(f"Draft competitor target '{slug}' created from {url}", "vendors_endpoint")
    return _target_view(created)


@router.post(
    "/targets/{slug}/approve",
    responses={
        404: {"description": "No DB target."},
        409: {"description": "File targets are always approved."},
        422: {"description": "The target points at one of our own stores."},
    },
)
async def approve_vendor_target(slug: str, payload: Optional[ApproveRequest] = None) -> Dict[str, Any]:
    """✅ AAD-1: approve a draft target so scrape runs read it.

    Idempotent: approving an approved target refreshes `approved_at`/`by`.
    """
    repo = _target_repository()
    try:
        existing = repo.get(slug)
        if existing is None:
            if any(t.slug.lower() == slug.lower() for t in all_targets(include_disabled=True)):
                raise HTTPException(status_code=409, detail=f"'{slug}' lives in VENDOR_TARGETS_FILE and is always approved.")
            raise HTTPException(status_code=404, detail=f"No vendor target '{slug}'.")
        try:
            check_not_owned(existing)
        except VendorTargetConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        approved = repo.approve(slug, payload.approved_by if payload else None)
    finally:
        repo.connection.close()
    if approved is None:
        raise HTTPException(status_code=404, detail=f"No vendor target '{slug}'.")
    return _target_view(approved)


@router.post(
    "/discover",
    responses={422: {"description": "Not a public http(s) URL, or one of our own stores."}},
)
async def discover_from_url(payload: DiscoverRequest) -> Dict[str, Any]:
    """🔎 AAD-1: preview selector-free discovery for a URL. Nothing is stored.

    Tries the WooCommerce Store API, Shopify `products.json`, then sitemaps +
    schema.org JSON-LD (microdata / OpenGraph as a last resort), and returns
    one reading per variant with its size label, price, currency, stock and
    the method used, plus the number of requests made. Same politeness as a
    run (robots.txt, pacing, request budget, no retries), so a preview of a
    sitemap-only store can take tens of seconds; keep `max_products` small.
    """
    url = payload.url.strip()
    _check_public_url(url)
    return await run_in_threadpool(preview_discovery, url, payload.max_products, payload.currency)


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
            detail="No enabled, approved vendor targets match this request. "
            "Add, enable or approve one first.",
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
    offset: Annotated[int, Query(ge=0, description="Rows to skip (pagination).")] = 0,
) -> Dict[str, Any]:
    """🚩 The review queue.

    Every reading the scraper did not trust enough to stand on its own: a
    price that moved more than the delta threshold, a low-confidence
    extraction, a page with no readable price, a blocked host. None of these
    has replaced a previously accepted value.
    """
    repo = _repository()
    try:
        rows = repo.list_flagged(limit=limit, vendor=vendor, offset=offset)
        total = repo.count_flagged(vendor=vendor)
    finally:
        repo.connection.close()
    return {
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "vendor": vendor,
        "observations": rows,
    }


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
