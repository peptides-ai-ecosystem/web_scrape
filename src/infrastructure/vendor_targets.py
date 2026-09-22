"""Loads competitor scrape targets from a configuration file.

Targets are **configuration, not code** (peptides-platform#288). A site is
added, paused (``"enabled": false``) or removed by editing one JSON file and
restarting — never by changing a Python module. That matters beyond
convenience: when a site owner asks us to stop, the person handling it must be
able to do so without a deploy.

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

from src.core.vendor_models import FieldSelectors, VendorTarget

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
        out.append(candidate)
    return tuple(out)


def parse_target(raw: Dict[str, Any]) -> VendorTarget:
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

    return VendorTarget(
        slug=slug,
        name=str(raw.get("name") or slug),
        product_urls=_validated_urls(raw.get("product_urls"), slug),
        selectors=selectors,
        currency=currency,
        enabled=bool(raw.get("enabled", True)),
        min_request_interval_seconds=interval,
        max_products_per_run=max_products,
    )


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
    from src.config import VENDOR_TARGETS_FILE

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
