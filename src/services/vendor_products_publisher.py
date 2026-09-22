"""The seam where scraped observations would reach `vendor_products` (#288).

peptides-platform#288 asks for scraped competitor listings to be written into
"the same ``vendor_products`` table (source = 'scraper')". **This service does
not do that, and this module exists to say exactly why, and to be the single
place that changes when it can.**

Four findings, each independently blocking:

1. **This service cannot reach that database.** ``vendor_products`` lives in
   the peptides-platform database. ``web_scrape`` has exactly one
   ``DATABASE_URL`` (``src/config.py``), pointing at its own peptide/graph
   store, and no configuration, credential or client for the platform's
   database. Inventing a second connection string here would be fabricating
   access we were not given.

2. **There is no ``source`` column.** ``vendor_products`` (migration
   ``0102_vendor_products.sql``) has ``id, vendor, wc_product_id,
   wc_variation_id, peptide_slug, match_source, match_confidence,
   product_name, sku, price, regular_price, currency, stock_status,
   stock_quantity, permalink, is_active, last_seen_at, created_at,
   updated_at`` — and nothing else as of migration 0109. ``match_source`` is
   *not* it: it records how ``peptide_slug`` was decided (``override``,
   ``exact``, ``alias``, ``fuzzy``, ``ignored``, ``unmatched``), so writing
   ``'scraper'`` into it would corrupt the admin's unmatched queue rather than
   mark provenance. The distinguishability the issue asks for therefore does
   not exist yet and cannot be faked from this side.

3. **The Woo-shaped key does not fit a scraped row.** ``wc_product_id`` is
   ``NOT NULL`` and the unique index is
   ``(vendor, wc_product_id, wc_variation_id)``. A competitor's page has no
   WooCommerce product id. Satisfying the key would mean synthesising fake Woo
   ids, which is precisely how a scraped guess would become indistinguishable
   from a vendor's own published price.

4. **#263 declared that table single-writer.** Its schema comment states the
   table is "written only by the sync — the nightly cron and the product-saved
   webhook". Adding a second writer is a decision for #263's owners to take in
   their repo, not one to take here by writing rows anyway. Nothing in this
   change loosens it: we add no column, no grant, no connection, and no
   outbound write.

**What we do instead:** accepted observations are stored in this service's own
``vendor_price_observations`` table with full provenance and confidence, and
exposed over the API. Anything that wants competitor prices can read them
from there today.

**What unblocks the direct write**, as a peptides-platform change:

* add ``source VARCHAR(16) NOT NULL DEFAULT 'woo'`` (values ``woo`` |
  ``scraper``) to ``vendor_products``, and make every existing read filter on
  it so a scraped guess cannot be served where a vendor's own price is meant;
* make ``wc_product_id`` nullable and add a scraper-shaped unique key, e.g.
  ``unique(vendor, source, listing_url)`` partial on ``source = 'scraper'``;
* decide whether scraped rows may set ``peptide_slug`` at all, or whether they
  always land ``unmatched`` for an admin;
* expose an authenticated ingest endpoint (this service holds no platform DB
  credentials and should not start holding any — an HTTP call through the
  gateway is the right shape).

Once that exists, implement :meth:`VendorProductsPublisher._send` against it
and flip ``VENDOR_PRODUCTS_PUBLISH_ENABLED``. Until then the publisher is a
loud no-op: it never silently succeeds.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Sequence

from src.core.vendor_models import ReviewStatus, VendorObservation

logger = logging.getLogger(__name__)


#: Value this service would write into a future ``vendor_products.source``
#: column. Kept here so the platform-side migration and this service agree on
#: one spelling when the seam is closed.
SCRAPER_SOURCE = "scraper"


class VendorProductsPublishUnavailable(RuntimeError):
    """Raised when publishing is switched on but no channel exists."""


@dataclass(frozen=True)
class PublishResult:
    published: int
    skipped: int
    reason: str

    def to_dict(self) -> dict:
        return {"published": self.published, "skipped": self.skipped, "reason": self.reason}


_UNAVAILABLE_REASON = (
    "vendor_products publishing is not implemented: the platform table has no "
    "'source' column, requires a non-null wc_product_id, and this service has "
    "no connection to the platform database. See the module docstring in "
    "src/services/vendor_products_publisher.py for the platform-side changes "
    "that would unblock it (peptides-platform#288, #263)."
)


class VendorProductsPublisher:
    """Would forward accepted observations to the platform. Currently cannot.

    Args:
        enabled: from ``VENDOR_PRODUCTS_PUBLISH_ENABLED``. Turning it on
            without an implementation raises rather than pretending — an
            operator who thinks prices are flowing must not be left believing
            that silently.
    """

    def __init__(self, enabled: bool = False):
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def publish(self, observations: Sequence[VendorObservation]) -> PublishResult:
        publishable: List[VendorObservation] = [
            o
            for o in observations
            if o.review_status is ReviewStatus.ACCEPTED and o.price is not None
        ]
        skipped = len(observations) - len(publishable)

        if not self._enabled:
            if publishable:
                logger.info(
                    "%d accepted observation(s) available; vendor_products publishing "
                    "is disabled, they remain in vendor_price_observations.",
                    len(publishable),
                )
            return PublishResult(
                published=0,
                skipped=len(observations),
                reason="publishing disabled (VENDOR_PRODUCTS_PUBLISH_ENABLED=false)",
            )

        return self._send(publishable, skipped)

    def _send(self, publishable: Sequence[VendorObservation], skipped: int) -> PublishResult:
        """The unimplemented half of the seam."""
        raise VendorProductsPublishUnavailable(_UNAVAILABLE_REASON)
