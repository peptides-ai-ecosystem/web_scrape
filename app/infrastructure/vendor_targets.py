"""Competitor scrape targets: parsing, the configuration file, and merging.

Targets are **configuration, not code** (peptides-platform#288). Since the
admin "Scrape" tab (CEO feedback round 2, P2) they are primarily managed
through the API and stored in ``vendor_scrape_targets``
(:mod:`app.repositories.vendor_target`). The JSON file named
by ``VENDOR_TARGETS_FILE`` is kept as a seed / fallback: a file target is used
only while no DB target has the same slug, so the DB always wins and an admin
can take a file target over by saving it once.

Either way a site is added, paused (``"enabled": false``) or removed without a
deploy — when a site owner asks us to stop, the person handling it must be
able to do so immediately.

Failure behaviour is deliberately quiet-and-empty. A missing or malformed file
yields *no targets*, so the scraper does nothing, rather than a crash that
takes the whole service's scheduler down, and rather than a hardcoded default
list that would keep hitting a site someone thought they had removed.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from datetime import datetime

from app.core.owned_stores import owned_reason
from app.core.vendor_models import FieldSelectors, TargetReviewState, VendorTarget
from app.infrastructure.url_safety import UnsafeTargetURLError, check_url

logger = logging.getLogger(__name__)


class VendorTargetConfigError(ValueError):
    """A target entry is structurally unusable."""


def _as_selector_tuple(value: Any, field_name: str, slug: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise VendorTargetConfigError(
            f"target '{slug}': selectors.{field_name} must be a string or list of strings"
        )
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise VendorTargetConfigError(
                f"target '{slug}': selectors.{field_name} contains a non-string or empty selector"
            )
        out.append(item.strip())
    return tuple(out)


def _validated_urls(value: Any, slug: str) -> Tuple[str, ...]:
    if not value:
        return ()
    if not isinstance(value, (list, tuple)):
        raise VendorTargetConfigError(f"target '{slug}': product_urls must be a list")
    out = []
    for item in value:
        if not isinstance(item, str):
            raise VendorTargetConfigError(f"target '{slug}': product_urls must be strings")
        candidate = item.strip()
        parsed = urlsplit(candidate)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise VendorTargetConfigError(
                f"target '{slug}': '{candidate}' is not an absolute http(s) URL"
            )
        _refuse_internal(candidate, "product_urls", slug)
        out.append(candidate)
    return tuple(out)


def _refuse_internal(url: str, field_name: str, slug: str, *, resolve: bool = False) -> None:
    """SSRF guard (see :mod:`app.infrastructure.url_safety`).

    On every parse only what needs no DNS is checked (IP literals such as
    127.0.0.1 or 169.254.169.254, ``localhost``), so loading the file or the
    DB never blocks on a resolver; :func:`check_target_addresses` adds the DNS
    check at save time and the fetchers repeat it on every request.
    """
    try:
        check_url(url, resolve=resolve)
    except UnsafeTargetURLError as exc:
        raise VendorTargetConfigError(
            f"target '{slug}': {field_name} '{url}' is not allowed: {exc}"
        ) from None


def check_target_addresses(target: VendorTarget) -> None:
    """Save-time SSRF check with DNS: every URL's host must resolve publicly.

    Raises :class:`VendorTargetConfigError` (the API answers 422). A host that
    does not resolve at all is refused too — there is nothing to vouch for.
    """
    for url in target.product_urls:
        _refuse_internal(url, "product_urls", target.slug, resolve=True)
    if target.listing_url:
        _refuse_internal(target.listing_url, "listing_url", target.slug, resolve=True)
    if target.store_url:
        _refuse_internal(target.store_url, "store_url", target.slug, resolve=True)


def target_urls(target: VendorTarget) -> List[str]:
    """Every URL a target points at (store, listing and product URLs)."""
    urls = [u for u in (target.store_url, target.listing_url) if u]
    return urls + list(target.product_urls)


def check_not_owned(target: VendorTarget) -> None:
    """Refuse a "competitor" target that is really one of our own stores.

    Competitor vendors stay separate from ours (AAD-1/AAD-2): our stores'
    prices arrive through the store import, never through the scraper.
    """
    reason = owned_reason(target_urls(target), (target.slug, target.platform_vendor_slug))
    if reason:
        raise VendorTargetConfigError(f"target '{target.slug}': {reason}")


def _optional_url(value: Any, field_name: str, slug: str) -> Optional[str]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise VendorTargetConfigError(f"target '{slug}': {field_name} must be a string")
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise VendorTargetConfigError(
            f"target '{slug}': {field_name} '{candidate}' is not an absolute http(s) URL"
        )
    _refuse_internal(candidate, field_name, slug)
    return candidate


def parse_target(raw: Dict[str, Any], *, source: str = "file") -> VendorTarget:
    """Build one :class:`VendorTarget` from a config dict, validating it."""
    if not isinstance(raw, dict):
        raise VendorTargetConfigError("each target must be a JSON object")

    slug = str(raw.get("slug") or "").strip()
    if not slug:
        raise VendorTargetConfigError("target is missing a 'slug'")

    selectors_raw = raw.get("selectors") or {}
    if not isinstance(selectors_raw, dict):
        raise VendorTargetConfigError(f"target '{slug}': 'selectors' must be an object")

    selectors = FieldSelectors(
        price=_as_selector_tuple(selectors_raw.get("price"), "price", slug),
        stock=_as_selector_tuple(selectors_raw.get("stock"), "stock", slug),
        coa=_as_selector_tuple(selectors_raw.get("coa"), "coa", slug),
        product_name=_as_selector_tuple(
            selectors_raw.get("product_name"), "product_name", slug
        ),
        variant=_as_selector_tuple(selectors_raw.get("variant"), "variant", slug),
    )

    currency = raw.get("currency")
    if currency is not None:
        currency = str(currency).strip().upper() or None
        if currency and len(currency) != 3:
            raise VendorTargetConfigError(
                f"target '{slug}': currency must be a 3-letter ISO-4217 code"
            )

    max_products = raw.get("max_products_per_run")
    if max_products is not None:
        max_products = int(max_products)
        if max_products < 1:
            raise VendorTargetConfigError(
                f"target '{slug}': max_products_per_run must be >= 1 when set"
            )

    interval = float(raw.get("min_request_interval_seconds", 5.0))
    if interval < 0:
        raise VendorTargetConfigError(
            f"target '{slug}': min_request_interval_seconds cannot be negative"
        )

    listing_url = _optional_url(raw.get("listing_url"), "listing_url", slug)
    link_selector = raw.get("listing_link_selector")
    link_selector = str(link_selector).strip() if link_selector else None
    if listing_url and not link_selector and selectors.price:
        # A selector target reads product links off the listing page with
        # this selector. A selector-free target (no price selector, AAD-1)
        # uses the listing URL as a discovery seed instead and needs none.
        raise VendorTargetConfigError(
            f"target '{slug}': listing_url needs a listing_link_selector "
            "(the CSS selector for product links on that page)"
        )

    platform_vendor_slug = str(raw.get("platform_vendor_slug") or "").strip().lower() or None
    store_url = _optional_url(raw.get("store_url"), "store_url", slug)

    review_raw = str(raw.get("review_state") or TargetReviewState.APPROVED.value).strip().lower()
    try:
        review_state = TargetReviewState(review_raw)
    except ValueError:
        raise VendorTargetConfigError(
            f"target '{slug}': review_state must be one of "
            f"{sorted(s.value for s in TargetReviewState)}"
        ) from None
    approved_at = raw.get("approved_at")
    if isinstance(approved_at, str):
        try:
            approved_at = datetime.fromisoformat(approved_at)
        except ValueError:
            approved_at = None
    if not isinstance(approved_at, datetime):
        approved_at = None
    approved_by = str(raw.get("approved_by") or "").strip() or None

    return VendorTarget(
        slug=slug,
        name=str(raw.get("name") or slug),
        product_urls=_validated_urls(raw.get("product_urls"), slug),
        selectors=selectors,
        currency=currency,
        enabled=bool(raw.get("enabled", True)),
        min_request_interval_seconds=interval,
        max_products_per_run=max_products,
        listing_url=listing_url,
        listing_link_selector=link_selector,
        platform_vendor_slug=platform_vendor_slug,
        source=source,
        store_url=store_url,
        review_state=review_state,
        approved_at=approved_at,
        approved_by=approved_by,
    )


def merge_targets(
    db_targets: Sequence[VendorTarget],
    file_targets: Sequence[VendorTarget],
    *,
    include_disabled: bool = False,
) -> List[VendorTarget]:
    """DB targets, plus file targets whose slug the DB does not define.

    The DB wins on a slug clash — including a *disabled* DB row, which is how
    an admin pauses a site that is also in the file. ``include_disabled``
    filters only after the merge for exactly that reason.
    """
    merged: List[VendorTarget] = []
    seen: set = set()
    for target in list(db_targets) + list(file_targets):
        key = target.slug.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(target)
    if include_disabled:
        return merged
    return [t for t in merged if t.enabled]


def load_targets(
    path: Optional[Path] = None, *, include_disabled: bool = False
) -> List[VendorTarget]:
    """Read every configured target.

    Args:
        path: config file; defaults to ``settings.VENDOR_TARGETS_FILE``.
        include_disabled: return ``enabled: false`` targets too (the API's
            target listing wants them, a scrape run does not).

    Returns an empty list when the file is absent or unreadable — see the
    module docstring for why that is not an exception.
    """
    from app.core.config import VENDOR_TARGETS_FILE

    target_path = Path(path) if path is not None else Path(VENDOR_TARGETS_FILE)

    if not target_path.is_file():
        logger.warning(
            "Vendor targets file %s not found — competitor scraping is a no-op.",
            target_path,
        )
        return []

    try:
        raw = json.loads(target_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Vendor targets file %s is unreadable: %s", target_path, exc)
        return []

    entries: Sequence[Any]
    if isinstance(raw, dict):
        entries = raw.get("targets") or []
    elif isinstance(raw, list):
        entries = raw
    else:
        logger.error("Vendor targets file %s must hold a list or {'targets': [...]}.", target_path)
        return []

    targets: List[VendorTarget] = []
    seen: set = set()
    for entry in entries:
        try:
            target = parse_target(entry)
        except (VendorTargetConfigError, TypeError, ValueError) as exc:
            # One bad entry must not silence the rest, and must not be guessed at.
            logger.error("Skipping invalid vendor target: %s", exc)
            continue
        if target.slug in seen:
            logger.error("Duplicate vendor target slug '%s' — keeping the first.", target.slug)
            continue
        seen.add(target.slug)
        if target.enabled or include_disabled:
            targets.append(target)

    return targets
