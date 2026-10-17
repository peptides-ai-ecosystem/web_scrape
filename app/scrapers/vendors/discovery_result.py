"""What one URL-only discovery found: the result types and the size check.

Split out of url_discovery.py to keep that file under 400 lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from app.core.vendor_models import ProductReading, ScrapeStatus

#: A size/amount in a product name: "10mg", "5 mg", "500mcg", "10ml", "60 caps".
_SIZE_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|g|ml|iu|units?|caps?|capsules|tabs?|tablets|vials?|kits?|pcs)\b",
    re.IGNORECASE,
)
#: Confidence for a reading with no size anywhere: the platform import matches
#: competitor prices by size, so a size-less price is held for review instead
#: of being accepted and then refused by the import (e.g. a JSON-LD Offer on a
#: multi-size page that only publishes the default size's price).
NO_SIZE_CONFIDENCE = 0.55


def has_size(reading: ProductReading) -> bool:
    return bool(reading.variant_label) or bool(_SIZE_RE.search(reading.product_name or ""))


def hold_sizeless(result: DiscoveryResult) -> None:
    held = 0
    for index, reading in enumerate(result.readings):
        if reading.price is not None and not has_size(reading) and reading.confidence > NO_SIZE_CONFIDENCE:
            result.readings[index] = replace(reading, confidence=NO_SIZE_CONFIDENCE)
            held += 1
    if held:
        result.notes.append(f"{held} reading(s) name no size; held for review (the import matches prices by size)")


@dataclass
class DiscoveryFailure:
    url: str
    status: ScrapeStatus
    detail: str


@dataclass
class DiscoveryResult:
    """What one discovery found, and how."""

    seed_url: str
    method: str | None = None
    readings: list[ProductReading] = field(default_factory=list)
    products_seen: int = 0
    requests_made: int = 0
    notes: list[str] = field(default_factory=list)
    failures: list[DiscoveryFailure] = field(default_factory=list)

    def to_dict(self, include_readings: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "seed_url": self.seed_url,
            "method": self.method,
            "products_seen": self.products_seen,
            "variants_found": len(self.readings),
            "priced": sum(1 for r in self.readings if r.price is not None),
            "requests_made": self.requests_made,
            "notes": list(self.notes),
            "failures": [{"url": f.url, "status": f.status.value, "detail": f.detail} for f in self.failures],
        }
        if include_readings:
            out["readings"] = [
                {
                    "url": r.url,
                    "page_url": r.page_url,
                    "product_name": r.product_name,
                    "variant_label": r.variant_label,
                    "sku": r.sku,
                    "price": str(r.price) if r.price is not None else None,
                    "currency": r.currency,
                    "stock_status": r.stock_status.value if r.stock_status else None,
                    "method": r.method,
                    "confidence": round(r.confidence, 4),
                }
                for r in self.readings
            ]
        return out
