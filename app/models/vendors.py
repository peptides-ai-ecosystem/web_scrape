"""Request models for the competitor vendor-pricing API (``/api/v1/vendors``)."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.vendor_models import VendorTarget
from app.infrastructure.vendor_targets import (
    VendorTargetConfigError,
    check_not_owned,
    check_target_addresses,
    parse_target,
)


class VendorScrapeRequest(BaseModel):
    """On-demand trigger for a competitor scrape pass."""

    vendors: list[str] | None = Field(
        None,
        description="Target slugs to scrape. `null` means every **enabled** target. "
        "Unknown slugs are ignored, not guessed at.",
        examples=[None, ["competitor-a"]],
    )
    limit_per_vendor: int | None = Field(
        None,
        description="Cap on product URLs fetched per vendor this run. `null` means "
        "the vendor's own `max_products_per_run`, or all of them.",
        ge=1,
        examples=[None, 5],
    )

    @field_validator("vendors")
    @classmethod
    def validate_vendors(cls, v):
        if v is None:
            return v
        cleaned = [s.strip() for s in v if isinstance(s, str) and s.strip()]
        if not cleaned:
            raise ValueError("vendors must be a list of non-empty slugs, or null.")
        return cleaned


class ReviewRequest(BaseModel):
    """A human's verdict on a flagged observation."""

    decision: str = Field(
        ...,
        description="`accept` promotes the reading to the current value; "
        "`reject` discards it and leaves the previously accepted value standing.",
        examples=["accept", "reject"],
    )
    reviewer: str | None = Field(None, description="Who reviewed it — recorded for the audit trail.", max_length=255)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v):
        normalised = (v or "").strip().lower()
        if normalised not in {"accept", "reject"}:
            raise ValueError("decision must be 'accept' or 'reject'.")
        return normalised


class TargetSelectors(BaseModel):
    """Ordered CSS selector candidates per field — primary first."""

    price: list[str] = Field(default_factory=list)
    stock: list[str] = Field(default_factory=list)
    coa: list[str] = Field(default_factory=list)
    product_name: list[str] = Field(default_factory=list)
    #: Optional: selected size/variant, appended to the product name.
    variant: list[str] = Field(default_factory=list)


class TargetPayload(BaseModel):
    """A competitor target as the admin drawer edits it.

    Selectors are optional (AAD-1): a target with no price selector is read
    without selectors from its ``store_url`` / product URLs (WooCommerce Store
    API, Shopify products.json, sitemaps + JSON-LD). ``review_state`` is not
    editable here — see ``POST /targets/{slug}/approve``.
    """

    slug: str = Field(
        ...,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$",
        description="Stable id (lowercase, digits, `-`/`_`). Immutable after create.",
    )
    name: str = Field(..., min_length=1, max_length=255)
    enabled: bool = True
    product_urls: list[str] = Field(default_factory=list, max_length=500)
    listing_url: str | None = None
    listing_link_selector: str | None = Field(None, max_length=500)
    selectors: TargetSelectors = Field(default_factory=TargetSelectors)
    currency: str | None = Field(None, min_length=3, max_length=3)
    min_request_interval_seconds: float = Field(5.0, ge=0, le=3600)
    max_products_per_run: int | None = Field(None, ge=1, le=10000)
    platform_vendor_slug: str | None = Field(
        None,
        max_length=255,
        description="Platform `vendors.slug` the prices are imported onto. Empty = slug.",
    )
    store_url: str | None = Field(
        None,
        max_length=2048,
        description="AAD-1: a store's home, shop or product URL. With no price selector "
        "the target is read without selectors from this URL.",
    )

    def to_target(self, **state: Any) -> VendorTarget:
        if not self.product_urls and not self.listing_url and not self.store_url:
            raise VendorTargetConfigError("give a store URL, product URLs or a listing URL")
        target = parse_target({**self.model_dump(), **state}, source="db")
        # Competitor vendors stay separate from ours (422).
        check_not_owned(target)
        # SSRF: refuse hosts that resolve to internal addresses (422).
        check_target_addresses(target)
        return target


class FromUrlRequest(BaseModel):
    """AAD-1: a competitor target from nothing but a URL."""

    url: str = Field(..., min_length=8, max_length=2048, description="Store home, shop or product URL.")
    name: str | None = Field(None, max_length=255, description="Defaults to the host name.")
    slug: str | None = Field(
        None,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$",
        description="Defaults to one derived from the host (glpeptides.is -> glpeptides-is).",
    )
    currency: str | None = Field(None, min_length=3, max_length=3)
    platform_vendor_slug: str | None = Field(None, max_length=255)
    max_products_per_run: int | None = Field(None, ge=1, le=10000)


class ApproveRequest(BaseModel):
    approved_by: str | None = Field(None, max_length=255, description="Recorded for the audit trail.")


class DiscoverRequest(BaseModel):
    """Dry-run discovery for one URL (nothing stored)."""

    url: str = Field(..., min_length=8, max_length=2048)
    max_products: int = Field(5, ge=1, le=25, description="Products (not variants) to read.")
    currency: str | None = Field(None, min_length=3, max_length=3)
