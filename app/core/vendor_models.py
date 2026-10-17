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
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

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


class TargetReviewState(str, Enum):
    """Whether an admin has validated a competitor target (AAD-1).

    A target created from a bare store URL starts as ``draft``: it is listed in
    the admin Scrape tab and can be previewed, but no scrape run reads it until
    an admin approves it. Targets configured with selectors by an admin are
    ``approved`` from the start, as they always were.
    """

    DRAFT = "draft"
    APPROVED = "approved"


class DiscoveryMode(str, Enum):
    """How a target's prices are read."""

    #: CSS selectors from the target's configuration (the original mode).
    SELECTORS = "selectors"
    #: No selectors: Store API / products.json / sitemap + JSON-LD (AAD-1).
    AUTO = "auto"


# ---------------------------------------------------------------------------
# Target configuration (API-managed in the DB, with the file as seed/fallback —
# see infrastructure/vendor_targets)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSelectors:
    """Ordered CSS selector candidates per field.

    Order is meaningful: the first entry is the selector we believe is the
    vendor's real price element, later entries are progressively weaker
    fallbacks. :mod:`app.scrapers.vendors.vendor_confidence` discounts a field that
    only matched on a fallback, because "we found *a* number somewhere on the
    page" is a weaker claim than "we found the element we were told to read".
    """

    price: tuple[str, ...] = ()
    stock: tuple[str, ...] = ()
    coa: tuple[str, ...] = ()
    product_name: tuple[str, ...] = ()
    #: Optional: the selected size/variant (e.g. ``button[aria-pressed=true]``
    #: on a multi-size page whose ``<h1>`` carries no size). Its text is
    #: appended to the product name; it is not scored for confidence.
    variant: tuple[str, ...] = ()


@dataclass(frozen=True)
class VendorTarget:
    """One competitor site we have been configured to read.

    Targets come from configuration — the ``vendor_scrape_targets`` table
    (managed through the admin API) or the targets file — never from code, so
    a site can be removed, or paused with ``enabled: false``, without a deploy.
    """

    slug: str
    name: str
    product_urls: tuple[str, ...] = ()
    selectors: FieldSelectors = field(default_factory=FieldSelectors)
    #: ISO-4217 fallback used only when the page states no currency symbol.
    currency: str | None = None
    enabled: bool = True
    #: Politeness floor for this host, in seconds between requests. The
    #: effective delay is the larger of this and robots.txt's Crawl-delay.
    min_request_interval_seconds: float = 5.0
    #: Hard cap on URLs fetched from this host in one run.
    max_products_per_run: int | None = None
    #: Optional category/listing page. When set, product URLs are discovered
    #: from it (links matching ``listing_link_selector`` on the same host) in
    #: addition to ``product_urls``. The listing page itself goes through the
    #: same robots.txt and rate-limit gates as a product page.
    listing_url: str | None = None
    listing_link_selector: str | None = None
    #: ``vendors.slug`` on the platform this competitor's prices land on when
    #: an admin imports them into PeptiPrices. ``None`` means "same as slug".
    platform_vendor_slug: str | None = None
    #: Where the target came from: ``db`` (managed through the API) or
    #: ``file`` (VENDOR_TARGETS_FILE, the seed / fallback).
    source: str = "file"
    #: A store's home, shop or product URL for selector-free discovery (AAD-1).
    store_url: str | None = None
    #: ``draft`` targets are never scraped by a run until an admin approves.
    review_state: TargetReviewState = TargetReviewState.APPROVED
    approved_at: datetime | None = None
    approved_by: str | None = None
    #: Always ``competitor``: our own stores are refused as targets. Exposed so
    #: the platform can tell scraped competitor vendors apart without env lists.
    kind: str = "competitor"

    @property
    def discovery_mode(self) -> DiscoveryMode:
        """Selectors when a price selector is configured, otherwise auto."""
        return DiscoveryMode.SELECTORS if self.selectors.price else DiscoveryMode.AUTO

    @property
    def is_approved(self) -> bool:
        return self.review_state is TargetReviewState.APPROVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "enabled": self.enabled,
            "product_urls": list(self.product_urls),
            "listing_url": self.listing_url,
            "listing_link_selector": self.listing_link_selector,
            "currency": self.currency,
            "min_request_interval_seconds": self.min_request_interval_seconds,
            "max_products_per_run": self.max_products_per_run,
            "platform_vendor_slug": self.platform_vendor_slug,
            "source": self.source,
            "store_url": self.store_url,
            "discovery_mode": self.discovery_mode.value,
            "review_state": self.review_state.value,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
            "kind": self.kind,
            "selectors": {
                "price": list(self.selectors.price),
                "stock": list(self.selectors.stock),
                "coa": list(self.selectors.coa),
                "product_name": list(self.selectors.product_name),
                "variant": list(self.selectors.variant),
            },
        }


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
    raw: str | None = None


@dataclass
class ExtractedFields:
    """What a single product page yielded.

    ``matches`` holds a :class:`FieldMatch` only for fields that both matched a
    selector *and* parsed into a usable value. A selector that matched an
    element containing unparseable junk leaves the field ``None`` and records
    no match, so it cannot inflate confidence.
    """

    product_name: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    stock_status: StockStatus | None = None
    coa_url: str | None = None
    matches: dict[str, FieldMatch] = field(default_factory=dict)


@dataclass
class ConfidenceBreakdown:
    """Per-field contributions to the score, so a low score is explainable."""

    score: float
    contributions: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "contributions": {k: round(v, 4) for k, v in self.contributions.items()},
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ProductReading:
    """One price reading for one variant, from selector-free discovery (AAD-1).

    ``url`` identifies the variant, not just the page (``?variant=`` on
    Shopify, ``#variant=`` otherwise), because the review gate and the
    accepted-latest read both key on ``(vendor, url)`` and two sizes of one
    product must not overwrite each other. ``product_name`` already carries
    the size label so the platform import can parse the size from it.
    """

    url: str
    product_name: str | None
    price: Decimal | None
    currency: str | None = None
    stock_status: StockStatus | None = None
    variant_label: str | None = None
    sku: str | None = None
    #: ``woo_store_api`` | ``shopify_json`` | ``json_ld`` | ``microdata`` | ``opengraph``
    method: str = "json_ld"
    confidence: float = 0.0
    #: The product page the reading belongs to (``url`` minus the variant key).
    page_url: str | None = None


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
    product_name: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    stock_status: StockStatus | None = None
    coa_url: str | None = None
    confidence: float = 0.0
    confidence_breakdown: dict[str, Any] = field(default_factory=dict)
    review_status: ReviewStatus = ReviewStatus.FLAGGED
    review_reason: ReviewReason | None = None
    #: Free text for the reviewer — e.g. "price moved 62% vs last accepted".
    review_note: str | None = None
    #: Non-fatal detail for BLOCKED/ERROR rows.
    failure_detail: str | None = None
    #: Size/variant label read from a store API or structured data (AAD-1).
    variant_label: str | None = None
    sku: str | None = None
    #: ``selectors`` or one of the :class:`ProductReading` methods.
    extraction_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
            "variant_label": self.variant_label,
            "sku": self.sku,
            "extraction_method": self.extraction_method,
        }


@dataclass
class VendorScrapeReport:
    """Aggregate outcome of one run, per :class:`ScrapeStatus`."""

    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    observations: list[VendorObservation] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {s.value: 0 for s in ScrapeStatus}
        for obs in self.observations:
            out[obs.status.value] += 1
        return out

    def review_counts(self) -> dict[str, int]:
        out: dict[str, int] = {s.value: 0 for s in ReviewStatus}
        for obs in self.observations:
            out[obs.review_status.value] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "urls_processed": len(self.observations),
            "status_counts": self.counts(),
            "review_counts": self.review_counts(),
            "observations": [o.to_dict() for o in self.observations],
        }
