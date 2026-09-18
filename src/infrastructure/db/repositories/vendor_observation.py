"""Repository for scraped competitor price observations (#288).

Backed by ``vendor_price_observations`` in **this service's** database — see
``migration_vendor_price_observations.sql``. Nothing here touches the
peptides-platform database or its ``vendor_products`` table.

The one rule this repository enforces on behalf of the rest of the system:
:meth:`latest_accepted` never returns a flagged row. A flagged reading is
stored, is visible in the review queue, and is *not* the current price. That
is what stops a broken selector from quietly overwriting a good value.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.core.vendor_models import (
    ReviewReason,
    ReviewStatus,
    ScrapeStatus,
    StockStatus,
    VendorObservation,
)
from src.infrastructure.db.base_repository import BaseRepository

logger = logging.getLogger(__name__)

_COLUMNS = """
    id, vendor, url, observed_at, status, product_name, price, currency,
    stock_status, coa_url, confidence, confidence_breakdown, review_status,
    review_reason, review_note, reviewed_at, reviewed_by, failure_detail
"""


def _row_to_observation(row: Optional[Dict[str, Any]]) -> Optional[VendorObservation]:
    """Hydrate a DB row. Unknown enum values degrade to ``None``, not a guess."""
    if not row:
        return None

    def _enum(enum_cls, value):
        if value is None:
            return None
        try:
            return enum_cls(value)
        except ValueError:
            logger.warning("Unknown %s value %r in vendor_price_observations.", enum_cls.__name__, value)
            return None

    breakdown = row.get("confidence_breakdown")
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except (TypeError, ValueError):
            breakdown = {}

    return VendorObservation(
        vendor=row["vendor"],
        url=row["url"],
        observed_at=row["observed_at"],
        status=_enum(ScrapeStatus, row.get("status")) or ScrapeStatus.OK,
        product_name=row.get("product_name"),
        price=row.get("price"),
        currency=row.get("currency"),
        stock_status=_enum(StockStatus, row.get("stock_status")),
        coa_url=row.get("coa_url"),
        confidence=float(row.get("confidence") or 0.0),
        confidence_breakdown=breakdown or {},
        review_status=_enum(ReviewStatus, row.get("review_status")) or ReviewStatus.FLAGGED,
        review_reason=_enum(ReviewReason, row.get("review_reason")),
        review_note=row.get("review_note"),
        failure_detail=row.get("failure_detail"),
    )


class VendorObservationRepository(BaseRepository):
    """Reads and writes ``vendor_price_observations``."""

    def latest_accepted(self, vendor: str, url: str) -> Optional[VendorObservation]:
        """The current trusted reading for a listing, or ``None``.

        Deliberately excludes ``flagged`` and ``rejected`` rows: the delta
        gate must compare against the last value a human would stand behind,
        not against the last thing the scraper happened to see.
        """
        row = self.execute_one(
            f"""SELECT {_COLUMNS}
                  FROM vendor_price_observations
                 WHERE vendor = %s AND url = %s
                   AND review_status = %s
                   AND price IS NOT NULL
                 ORDER BY observed_at DESC
                 LIMIT 1""",
            (vendor, url, ReviewStatus.ACCEPTED.value),
        )
        return _row_to_observation(row)

    def insert(self, observation: VendorObservation) -> int:
        """Store one observation; returns its id.

        Append-only. Nothing is updated in place, so a flagged reading can
        never destroy the accepted one it disagrees with — the history is the
        audit trail for "why did this price change?".
        """
        with self.get_cursor() as cur:
            cur.execute(
                """INSERT INTO vendor_price_observations
                       (vendor, url, observed_at, status, product_name, price,
                        currency, stock_status, coa_url, confidence,
                        confidence_breakdown, review_status, review_reason,
                        review_note, failure_detail)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    observation.vendor,
                    observation.url,
                    observation.observed_at,
                    observation.status.value,
                    observation.product_name,
                    observation.price,
                    observation.currency,
                    observation.stock_status.value if observation.stock_status else None,
                    observation.coa_url,
                    Decimal(str(round(observation.confidence, 3))),
                    json.dumps(observation.confidence_breakdown or {}),
                    observation.review_status.value,
                    observation.review_reason.value if observation.review_reason else None,
                    observation.review_note,
                    observation.failure_detail,
                ),
            )
            row = cur.fetchone()
            self._commit()
        return int(row["id"]) if row else 0

    def list_flagged(self, limit: int = 100, vendor: Optional[str] = None) -> List[Dict[str, Any]]:
        """The review queue, newest first."""
        if vendor:
            return self.execute_all(
                f"""SELECT {_COLUMNS}
                      FROM vendor_price_observations
                     WHERE review_status = %s AND vendor = %s
                     ORDER BY observed_at DESC
                     LIMIT %s""",
                (ReviewStatus.FLAGGED.value, vendor, limit),
            )
        return self.execute_all(
            f"""SELECT {_COLUMNS}
                  FROM vendor_price_observations
                 WHERE review_status = %s
                 ORDER BY observed_at DESC
                 LIMIT %s""",
            (ReviewStatus.FLAGGED.value, limit),
        )

    def resolve_review(
        self, observation_id: int, status: ReviewStatus, reviewer: Optional[str] = None
    ) -> int:
        """Record a human's decision on a flagged observation.

        Only ``accepted`` or ``rejected`` are meaningful here, and only a
        currently-flagged row can be resolved — so a review cannot silently
        un-accept a value that other things are already reading.
        """
        if status not in (ReviewStatus.ACCEPTED, ReviewStatus.REJECTED):
            raise ValueError("a review resolves to 'accepted' or 'rejected'")
        return self.execute_update(
            """UPDATE vendor_price_observations
                  SET review_status = %s,
                      reviewed_at = now(),
                      reviewed_by = %s
                WHERE id = %s
                  AND review_status = %s""",
            (status.value, reviewer, observation_id, ReviewStatus.FLAGGED.value),
        )
