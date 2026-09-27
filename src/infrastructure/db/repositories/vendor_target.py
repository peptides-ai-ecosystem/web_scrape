"""Repository for API-managed competitor scrape targets (CEO round 2, P2).

Backed by ``vendor_scrape_targets`` in **this service's** database — see
``migration_vendor_scrape_targets.sql``. Every row is validated through the
same :func:`~src.infrastructure.vendor_targets.parse_target` the file loader
uses, so a target cannot be stored in a shape the scraper would refuse.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.core.vendor_models import VendorTarget
from src.infrastructure.db.base_repository import BaseRepository
from src.infrastructure.vendor_targets import VendorTargetConfigError, parse_target

logger = logging.getLogger(__name__)

_COLUMNS = """
    id, slug, name, enabled, product_urls, listing_url, listing_link_selector,
    selectors, currency, min_request_interval_seconds, max_products_per_run,
    platform_vendor_slug, created_at, updated_at
"""


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return value


def row_to_target(row: Dict[str, Any]) -> VendorTarget:
    """Hydrate a DB row through the shared validator."""
    interval = row.get("min_request_interval_seconds")
    raw = {
        "slug": row["slug"],
        "name": row.get("name"),
        "enabled": row.get("enabled", True),
        "product_urls": _json(row.get("product_urls"), []),
        "listing_url": row.get("listing_url"),
        "listing_link_selector": row.get("listing_link_selector"),
        "selectors": _json(row.get("selectors"), {}),
        "currency": row.get("currency"),
        "min_request_interval_seconds": float(interval) if interval is not None else 5.0,
        "max_products_per_run": row.get("max_products_per_run"),
        "platform_vendor_slug": row.get("platform_vendor_slug"),
    }
    return parse_target(raw, source="db")


def _params(target: VendorTarget) -> tuple:
    return (
        target.name,
        target.enabled,
        json.dumps(list(target.product_urls)),
        target.listing_url,
        target.listing_link_selector,
        json.dumps(target.to_dict()["selectors"]),
        target.currency,
        Decimal(str(target.min_request_interval_seconds)),
        target.max_products_per_run,
        target.platform_vendor_slug,
    )


class VendorTargetRepository(BaseRepository):
    """CRUD over ``vendor_scrape_targets``."""

    def list_all(self) -> List[VendorTarget]:
        rows = self.execute_all(
            f"SELECT {_COLUMNS} FROM vendor_scrape_targets ORDER BY lower(slug)"
        )
        targets: List[VendorTarget] = []
        for row in rows:
            try:
                targets.append(row_to_target(row))
            except (VendorTargetConfigError, TypeError, ValueError) as exc:
                # A row edited by hand into an invalid shape must not stop the
                # rest from being scraped — and must not be guessed at.
                logger.error("Skipping invalid DB vendor target %r: %s", row.get("slug"), exc)
        return targets

    def get(self, slug: str) -> Optional[VendorTarget]:
        row = self.execute_one(
            f"SELECT {_COLUMNS} FROM vendor_scrape_targets WHERE lower(slug) = lower(%s)",
            (slug,),
        )
        return row_to_target(row) if row else None

    def create(self, target: VendorTarget) -> VendorTarget:
        with self.get_cursor() as cur:
            cur.execute(
                f"""INSERT INTO vendor_scrape_targets
                       (slug, name, enabled, product_urls, listing_url,
                        listing_link_selector, selectors, currency,
                        min_request_interval_seconds, max_products_per_run,
                        platform_vendor_slug)
                   VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s, %s)
                   RETURNING {_COLUMNS}""",
                (target.slug,) + _params(target),
            )
            row = cur.fetchone()
            self._commit()
        return row_to_target(row)

    def update(self, slug: str, target: VendorTarget) -> Optional[VendorTarget]:
        """Replace every editable field; the slug itself is immutable."""
        with self.get_cursor() as cur:
            cur.execute(
                f"""UPDATE vendor_scrape_targets
                       SET name = %s, enabled = %s, product_urls = %s::jsonb,
                           listing_url = %s, listing_link_selector = %s,
                           selectors = %s::jsonb, currency = %s,
                           min_request_interval_seconds = %s,
                           max_products_per_run = %s, platform_vendor_slug = %s,
                           updated_at = now()
                     WHERE lower(slug) = lower(%s)
                 RETURNING {_COLUMNS}""",
                _params(target) + (slug,),
            )
            row = cur.fetchone()
            self._commit()
        return row_to_target(row) if row else None

    def delete(self, slug: str) -> int:
        return self.execute_update(
            "DELETE FROM vendor_scrape_targets WHERE lower(slug) = lower(%s)", (slug,)
        )
