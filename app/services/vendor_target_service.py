"""Competitor scrape targets (``/api/v1/vendors/targets``, ``/discover``).

Targets live in ``vendor_scrape_targets`` (this service's own table); the
``VENDOR_TARGETS_FILE`` targets are a seed / fallback used only while no DB
target has the same slug. Slug checks, the views the admin Scrape tab reads
and every repository call are here; the endpoints only map errors to status
codes.
"""

import os
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import psycopg2

from app.core.config import (
    VENDOR_MIN_CONFIDENCE,
    VENDOR_PRICE_DELTA_THRESHOLD,
    VENDOR_SCRAPE_MIN_INTERVAL_SECONDS,
    VENDOR_SCRAPER_USER_AGENT,
    VENDOR_TARGETS_FILE,
)
from app.core.errors import ConflictError, InvalidInputError, NotFoundError, ServiceUnavailableError
from app.core.logging import log_info
from app.core.owned_stores import owned_reason
from app.core.vendor_models import DiscoveryMode, TargetReviewState, VendorTarget
from app.infrastructure.db.connection import DbConnection
from app.infrastructure.url_safety import UnsafeTargetURLError, check_url
from app.infrastructure.vendor_targets import (
    VendorTargetConfigError,
    check_not_owned,
    check_target_addresses,
    parse_target,
    target_urls,
)
from app.models.vendors import FromUrlRequest, TargetPayload
from app.repositories import VendorTargetRepository
from app.services.vendor_scrape_runner import all_targets, preview_discovery

_TARGET_STATES = {s.value for s in TargetReviewState}
_TARGET_MODES = {m.value for m in DiscoveryMode}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def db_url() -> str:
    """``DATABASE_URL``, or 503 when the server has none."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ServiceUnavailableError("DATABASE_URL is not configured.")
    return url


def _target_repository() -> VendorTargetRepository:
    return VendorTargetRepository(DbConnection(db_url()))


def _target_view(target: VendorTarget) -> dict[str, Any]:
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
        raise InvalidInputError(f"'{url}' is not an absolute http(s) URL.")
    owned = owned_reason([url])
    if owned:
        raise InvalidInputError(owned)
    try:
        check_url(url)
    except UnsafeTargetURLError as exc:
        raise InvalidInputError(f"'{url}' is not allowed: {exc}")


def _matches(target: VendorTarget, q: str) -> bool:
    needle = q.strip().lower()
    haystack = [target.slug, target.name, target.platform_vendor_slug or ""] + target_urls(target)
    return any(needle in (h or "").lower() for h in haystack)


def _in_any_source(slug: str) -> bool:
    return any(t.slug.lower() == slug.lower() for t in all_targets(include_disabled=True))


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_targets(
    limit: int | None,
    offset: int,
    q: str | None,
    review_state: str | None,
    discovery_mode: str | None,
) -> dict[str, Any]:
    """A page of targets (DB + file fallbacks) plus the politeness settings the tab shows."""
    if review_state and review_state not in _TARGET_STATES:
        raise InvalidInputError(f"review_state must be one of {sorted(_TARGET_STATES)}")
    if discovery_mode and discovery_mode not in _TARGET_MODES:
        raise InvalidInputError(f"discovery_mode must be one of {sorted(_TARGET_MODES)}")
    everything = all_targets(include_disabled=True)
    targets = list(everything)
    if review_state:
        targets = [t for t in targets if t.review_state.value == review_state]
    if discovery_mode:
        targets = [t for t in targets if t.discovery_mode.value == discovery_mode]
    if q and q.strip():
        targets = [t for t in targets if _matches(t, q)]
    total = len(targets)
    page = targets[offset : offset + limit] if limit is not None else targets[offset:]
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


def get_target(slug: str) -> dict[str, Any]:
    """One target by slug (DB first, then the file); 404 when neither has it."""
    for target in all_targets(include_disabled=True):
        if target.slug.lower() == slug.lower():
            return _target_view(target)
    raise NotFoundError(f"No vendor target '{slug}'.")


def check_discover_url(url: str) -> str:
    """The stripped URL, or 422 when it is not a public http(s) URL or is one of our own stores."""
    url = url.strip()
    _check_public_url(url)
    return url


def discover(
    url: str, max_products: int, currency: str | None, should_stop: Callable[[], bool] | None = None
) -> dict[str, Any]:
    """Dry-run selector-free discovery for one URL; nothing is stored. Blocking (network)."""
    url = check_discover_url(url)
    if should_stop is None:  # the synchronous route: no deadline hook
        return preview_discovery(url, max_products, currency)
    return preview_discovery(url, max_products, currency, should_stop=should_stop)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def create_target(payload: TargetPayload) -> dict[str, Any]:
    """Store a new target. With a price selector it is approved at once; without one it is a draft."""
    try:
        auto = not payload.selectors.price
        target = payload.to_target(review_state=(TargetReviewState.DRAFT if auto else TargetReviewState.APPROVED).value)
    except VendorTargetConfigError as exc:
        raise InvalidInputError(str(exc))
    repo = _target_repository()
    try:
        if repo.get(target.slug) is not None:
            raise ConflictError(f"Vendor target '{target.slug}' already exists.")
        created = repo.create(target)
    except psycopg2.errors.UniqueViolation:
        raise ConflictError(f"Vendor target '{target.slug}' already exists.")
    finally:
        repo.connection.close()
    return _target_view(created)


def update_target(slug: str, payload: TargetPayload) -> dict[str, Any]:
    """Replace a target; a file-only target is taken over into the DB. The slug is immutable."""
    if payload.slug.lower() != slug.lower():
        raise InvalidInputError("The slug cannot be changed.")
    repo = _target_repository()
    try:
        # review_state is not editable here: keep what the row has. A file
        # target taken over keeps "approved" (file targets always were).
        existing = repo.get(slug)
        state: dict[str, Any] = {}
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
        elif not payload.selectors.price and not _in_any_source(slug):
            # A brand-new selector-free target is a draft, however it is created.
            state = {"review_state": TargetReviewState.DRAFT.value}
        try:
            target = payload.to_target(**state)
        except VendorTargetConfigError as exc:
            raise InvalidInputError(str(exc))
        updated = repo.update(slug, target)
        if updated is None:
            updated = repo.create(target)
    finally:
        repo.connection.close()
    return _target_view(updated)


def delete_target(slug: str) -> None:
    """Remove a DB target (observations are kept); 409 for a file target, 404 for none."""
    repo = _target_repository()
    try:
        deleted = repo.delete(slug)
    finally:
        repo.connection.close()
    if not deleted:
        if _in_any_source(slug):
            raise ConflictError(f"'{slug}' is defined in VENDOR_TARGETS_FILE; save it disabled to pause it.")
        raise NotFoundError(f"No vendor target '{slug}'.")


def create_target_from_url(payload: FromUrlRequest) -> dict[str, Any]:
    """AAD-1: a draft, selector-free competitor target from a bare store URL."""
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
        raise InvalidInputError(str(exc))
    if _in_any_source(slug):
        raise ConflictError(f"Vendor target '{slug}' already exists.")
    repo = _target_repository()
    try:
        created = repo.create(target)
    except psycopg2.errors.UniqueViolation:
        raise ConflictError(f"Vendor target '{slug}' already exists.")
    finally:
        repo.connection.close()
    log_info(f"Draft competitor target '{slug}' created from {url}", "vendors_endpoint")
    return _target_view(created)


def approve_target(slug: str, approved_by: str | None) -> dict[str, Any]:
    """AAD-1: approve a draft so scrape runs read it. Idempotent."""
    repo = _target_repository()
    try:
        existing = repo.get(slug)
        if existing is None:
            if _in_any_source(slug):
                raise ConflictError(f"'{slug}' lives in VENDOR_TARGETS_FILE and is always approved.")
            raise NotFoundError(f"No vendor target '{slug}'.")
        try:
            check_not_owned(existing)
        except VendorTargetConfigError as exc:
            raise InvalidInputError(str(exc))
        approved = repo.approve(slug, approved_by)
    finally:
        repo.connection.close()
    if approved is None:
        raise NotFoundError(f"No vendor target '{slug}'.")
    return _target_view(approved)
