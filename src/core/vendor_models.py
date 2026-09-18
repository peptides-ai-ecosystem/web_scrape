"""Domain models for competitor vendor price scraping (peptides-platform#288).

Everything here is a plain dataclass with no I/O, so the scraping policy
(robots, rate limiting), the extraction, the confidence scoring and the
persistence layers can all be unit-tested against them without a browser or a
database.

House rule that shapes these models: **where the data is absent or
untrustworthy we store nothing rather than a placeholder.** Every scraped
field is therefore ``Optional`` and there is no "0.00", no "unknown" and no
empty-string sentinel anywhere in this module. A price we could not read is
``None``, and a ``None`` price must never be rendered as if it were free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class StockStatus(str, Enum):
    """Stock vocabulary, deliberately identical to the platform's.

    ``vendor_products.stock_status`` on the platform side stores Woo's
    ``instock`` / ``outofstock`` / ``onbackorder``. Using the same three
    strings means a future publisher does not have to translate, and an
    unreadable stock line stays ``None`` instead of defaulting to ``instock``
    (which would be a lie about someone else's shop).
    """

    IN_STOCK = "instock"
    OUT_OF_STOCK = "outofstock"
    ON_BACKORDER = "onbackorder"


class ScrapeStatus(str, Enum):
    """Why one product URL ended the way it did."""

    OK = "ok"
    #: robots.txt disallows the path for our user-agent — we never fetched it.
    ROBOTS_DISALLOWED = "robots_disallowed"
    #: The site refused us (403 / repeated 429 / repeated 5xx). Recorded, not
    #: worked around: no retry storm, no identity rotation, no CAPTCHA solving.
    BLOCKED = "blocked"
    #: Transport or browser failure.
    ERROR = "error"
    #: Target disabled in configuration, or the run's per-host budget was spent.
    SKIPPED = "skipped"


class ReviewStatus(str, Enum):
    """What a human still owes this observation."""

    #: Trustworthy enough to be treated as the current reading.
    ACCEPTED = "accepted"
    #: Stored, but must not replace a previously accepted value until reviewed.
    FLAGGED = "flagged"
    #: A reviewer looked and said no.
    REJECTED = "rejected"


class ReviewReason(str, Enum):
    """Why an observation was flagged. ``None`` on accepted observations."""

    LOW_CONFIDENCE = "low_confidence"
    PRICE_DELTA = "price_delta"
    NO_PRICE = "no_price"
    CURRENCY_CHANGED = "currency_changed"


# ---------------------------------------------------------------------------
# Target configuration (loaded from a file — see infrastructure/vendor_targets)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSelectors:
    """Ordered CSS selector candidates per field.

    Order is meaningful: the first entry is the selector we believe is the
    vendor's real price element, later entries are progressively weaker
    fallbacks. :mod:`src.services.vendor_confidence` discounts a field that
    only matched on a fallback, because "we found *a* number somewhere on the
    page" is a weaker claim than "we found the element we were told to read".
    """

    price: Tuple[str, ...] = ()
    stock: Tuple[str, ...] = ()
    coa: Tuple[str, ...] = ()
    product_name: Tuple[str, ...] = ()


@dataclass(frozen=True)
class VendorTarget:
    """One competitor site we have been configured to read.

    Targets come from a configuration file, never from code, so a site can be
    removed — or paused with ``enabled: false`` — without a deploy.
    """

    slug: str
    name: str
    product_urls: Tuple[str, ...] = ()
    selectors: FieldSelectors = field(default_factory=FieldSelectors)
    #: ISO-4217 fallback used only when the page states no currency symbol.
    currency: Optional[str] = None
    enabled: bool = True
    #: Politeness floor for this host, in seconds between requests. The
    #: effective delay is the larger of this and robots.txt's Crawl-delay.
    min_request_interval_seconds: float = 5.0
    #: Hard cap on URLs fetched from this host in one run.
    max_products_per_run: Optional[int] = None


# ---------------------------------------------------------------------------
# Extraction results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldMatch:
    """How one field was obtained — the raw input to confidence scoring."""

    #: Index into the target's selector list; 0 is the primary selector.
    selector_index: int
    selector: str
    #: The text we read before parsing, kept for debugging a bad extraction.
    raw: Optional[str] = None


@dataclass
class ExtractedFields:
    """What a single product page yielded.

    ``matches`` holds a :class:`FieldMatch` only for fields that both matched a
    selector *and* parsed into a usable value. A selector that matched an
    element containing unparseable junk leaves the field ``None`` and records
    no match, so it cannot inflate confidence.
    """

    product_name: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    stock_status: Optional[StockStatus] = None
    coa_url: Optional[str] = None
    matches: Dict[str, FieldMatch] = field(default_factory=dict)


@dataclass
class ConfidenceBreakdown:
    """Per-field contributions to the score, so a low score is explainable."""

    score: float
    contributions: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "contributions": {k: round(v, 4) for k, v in self.contributions.items()},
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------


@dataclass
class VendorObservation:
    """One reading of one competitor product page at one moment.

    This is an *observation*, not a fact about the vendor's catalogue: it is
    our guess at what their page said. It is stored with the confidence and
    the review status attached so that nothing downstream can read a price
    without also being able to see how much to trust it.
    """

    vendor: str
    url: str
    observed_at: datetime
    status: ScrapeStatus = ScrapeStatus.OK
    product_name: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    stock_status: Optional[StockStatus] = None
    coa_url: Optional[str] = None
    confidence: float = 0.0
    confidence_breakdown: Dict[str, Any] = field(default_factory=dict)
    review_status: ReviewStatus = ReviewStatus.FLAGGED
    review_reason: Optional[ReviewReason] = None
    #: Free text for the reviewer — e.g. "price moved 62% vs last accepted".
    review_note: Optional[str] = None
    #: Non-fatal detail for BLOCKED/ERROR rows.
    failure_detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe projection. Absent values stay ``None``, never ""."""
        return {
            "vendor": self.vendor,
            "url": self.url,
            "observed_at": self.observed_at.isoformat(),
            "status": self.status.value,
            "product_name": self.product_name,
            # Decimal -> str, never float: this is money.
            "price": str(self.price) if self.price is not None else None,
            "currency": self.currency,
            "stock_status": self.stock_status.value if self.stock_status else None,
            "coa_url": self.coa_url,
            "confidence": round(self.confidence, 4),
            "confidence_breakdown": self.confidence_breakdown,
            "review_status": self.review_status.value,
            "review_reason": self.review_reason.value if self.review_reason else None,
            "review_note": self.review_note,
            "failure_detail": self.failure_detail,
        }


@dataclass
class VendorScrapeReport:
    """Aggregate outcome of one run, per :class:`ScrapeStatus`."""

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    observations: List[VendorObservation] = field(default_factory=list)

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {s.value: 0 for s in ScrapeStatus}
        for obs in self.observations:
            out[obs.status.value] += 1
        return out

    def review_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {s.value: 0 for s in ReviewStatus}
        for obs in self.observations:
            out[obs.review_status.value] += 1
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "urls_processed": len(self.observations),
            "status_counts": self.counts(),
            "review_counts": self.review_counts(),
            "observations": [o.to_dict() for o in self.observations],
        }
