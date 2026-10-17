"""Competitor vendor price scraping endpoints (peptides-platform#288, CEO round 2 P2).

HTTP only — each route is a status mapping plus one call: targets go to
``app/services/vendor_target_service.py``, observations to
``app/services/vendor_observation_service.py`` and scrape runs to
``app/controllers/vendor_scrape_controller.py``. The pipeline itself lives in
``app/scrapers/vendors/vendor_scraper.py`` and its wiring in
``app/services/vendor_scrape_runner.py``.

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
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Query, Response
from fastapi.concurrency import run_in_threadpool

from app.api.errors import http_error
from app.controllers.vendor_scrape_controller import VendorScrapeController
from app.core.errors import ServiceError
from app.models.vendors import (
    ApproveRequest,
    DiscoverRequest,
    FromUrlRequest,
    ReviewRequest,
    TargetPayload,
    VendorScrapeRequest,
)
from app.services import vendor_observation_service, vendor_target_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


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
    try:
        return vendor_target_service.list_targets(limit, offset, q, review_state, discovery_mode)
    except ServiceError as exc:
        raise http_error(exc)


@router.get("/targets/{slug}", responses={404: {"description": "No such target."}})
async def get_vendor_target(slug: str) -> Dict[str, Any]:
    """One target by slug (DB first, then the file)."""
    try:
        return vendor_target_service.get_target(slug)
    except ServiceError as exc:
        raise http_error(exc)


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
        return vendor_target_service.create_target(payload)
    except ServiceError as exc:
        raise http_error(exc)


@router.put("/targets/{slug}", responses={422: {"description": "Invalid target."}})
async def update_vendor_target(slug: str, payload: TargetPayload) -> Dict[str, Any]:
    """✏️ Replace a target. A file-only target is taken over into the DB."""
    try:
        return vendor_target_service.update_target(slug, payload)
    except ServiceError as exc:
        raise http_error(exc)


@router.delete(
    "/targets/{slug}",
    status_code=204,
    responses={404: {"description": "No DB target."}, 409: {"description": "Target lives in the file."}},
)
async def delete_vendor_target(slug: str) -> Response:
    """🗑️ Remove a DB target. Observations already stored are kept (audit trail)."""
    try:
        vendor_target_service.delete_target(slug)
    except ServiceError as exc:
        raise http_error(exc)
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
    try:
        return vendor_target_service.create_target_from_url(payload)
    except ServiceError as exc:
        raise http_error(exc)


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
    try:
        return vendor_target_service.approve_target(slug, payload.approved_by if payload else None)
    except ServiceError as exc:
        raise http_error(exc)


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
    try:
        return await run_in_threadpool(
            vendor_target_service.discover, payload.url, payload.max_products, payload.currency
        )
    except ServiceError as exc:
        raise http_error(exc)


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
    try:
        return VendorScrapeController(background_tasks.add_task).trigger(request.vendors, request.limit_per_vendor)
    except ServiceError as exc:
        raise http_error(exc)


@router.get("/scrape/jobs")
async def list_vendor_scrape_jobs(
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    """Recent vendor scrape jobs, newest first (in-memory; cleared on restart)."""
    return VendorScrapeController.list_jobs(limit)


@router.get("/scrape/jobs/{job_id}", responses={404: {"description": "Unknown job."}})
async def get_vendor_scrape_job(job_id: str) -> Dict[str, Any]:
    """Status of one scrape: `progress` (0-100), `progress_detail` {done,total}, result."""
    try:
        return VendorScrapeController.get_job(job_id)
    except ServiceError as exc:
        raise http_error(exc)


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------


@router.get("/observations")
async def list_observations(
    vendor: Optional[str] = Query(None, description="Restrict to one vendor slug."),
    review_status: Optional[str] = Query(None, description="accepted | flagged | rejected"),
    status: Optional[str] = Query(None, description="ok | robots_disallowed | blocked | error | skipped"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """📋 Every reading, newest first, filterable by vendor / review status / scrape status."""
    try:
        return vendor_observation_service.list_observations(vendor, review_status, status, limit, offset)
    except ServiceError as exc:
        raise http_error(exc)


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
    return vendor_observation_service.list_flagged(limit, vendor, offset)


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
    return vendor_observation_service.list_latest_accepted(vendor)


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
    try:
        return vendor_observation_service.review(observation_id, request.decision, request.reviewer)
    except ServiceError as exc:
        raise http_error(exc)


