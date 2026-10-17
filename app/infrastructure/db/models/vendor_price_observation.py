"""``vendor_price_observations``: one reading of one competitor page at one moment.

Mirrors the baseline revision (``alembic/versions/4b1d0c2e9f10_*``). Readers
must filter on ``review_status = 'accepted'``.
"""

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Index, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB

from app.infrastructure.db.models.base import Base


class VendorPriceObservation(Base):
    __tablename__ = "vendor_price_observations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    vendor = Column(String(64), nullable=False)
    url = Column(Text, nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status = Column(String(32), nullable=False, server_default=text("'ok'"))
    product_name = Column(String(512))
    price = Column(Numeric(12, 4))
    currency = Column(String(3))
    stock_status = Column(String(32))
    coa_url = Column(Text)
    confidence = Column(Numeric(4, 3), nullable=False, server_default=text("0"))
    confidence_breakdown = Column(JSONB)
    review_status = Column(String(16), nullable=False, server_default=text("'flagged'"))
    review_reason = Column(String(32))
    review_note = Column(Text)
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(String(255))
    failure_detail = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    variant_label = Column(String(255))
    sku = Column(String(255))
    extraction_method = Column(String(32))

    __table_args__ = (
        CheckConstraint("price IS NULL OR price > 0", name="vendor_price_observations_price_positive"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="vendor_price_observations_confidence_range"),
        Index("vendor_price_observations_current_idx", vendor, url, review_status, observed_at.desc()),
        Index("vendor_price_observations_review_idx", review_status, observed_at.desc()),
        Index("vendor_price_observations_vendor_idx", vendor),
    )
