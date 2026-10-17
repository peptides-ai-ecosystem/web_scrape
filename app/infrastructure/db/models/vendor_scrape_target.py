"""``vendor_scrape_targets``: competitor targets managed from the admin Scrape tab.

Mirrors the baseline revision (``alembic/versions/4b1d0c2e9f10_*``). Columns are
documented in that revision.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.infrastructure.db.models.base import Base


class VendorScrapeTarget(Base):
    __tablename__ = "vendor_scrape_targets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    slug = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    enabled = Column(Boolean, nullable=False, server_default=text("true"))
    product_urls = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    listing_url = Column(Text)
    listing_link_selector = Column(Text)
    selectors = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    currency = Column(String(3))
    min_request_interval_seconds = Column(Numeric(8, 2), nullable=False, server_default=text("5.0"))
    max_products_per_run = Column(Integer)
    platform_vendor_slug = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    store_url = Column(Text)
    review_state = Column(String(16), nullable=False, server_default=text("'approved'"))
    approved_at = Column(DateTime(timezone=True))
    approved_by = Column(String(255))
    kind = Column(String(16), nullable=False, server_default=text("'competitor'"))

    __table_args__ = (
        CheckConstraint("length(trim(slug)) > 0", name="vendor_scrape_targets_slug_not_empty"),
        CheckConstraint(
            "min_request_interval_seconds >= 0", name="vendor_scrape_targets_interval_non_negative"
        ),
        CheckConstraint(
            "max_products_per_run IS NULL OR max_products_per_run >= 1",
            name="vendor_scrape_targets_max_products_positive",
        ),
        Index("vendor_scrape_targets_slug_uidx", func.lower(slug), unique=True),
    )
