"""SQLAlchemy models for the tables web_scrape owns, one file per table.

Used only as Alembic's target metadata (``alembic/env.py``); the repositories
keep their raw SQL. Platform tables (peptides, peptide_graph, ...) are never
modelled here: they belong to peptides-platform's Drizzle schema (XR-8).
"""

from app.infrastructure.db.models.base import VERSION_TABLE, Base
from app.infrastructure.db.models.vendor_price_observation import VendorPriceObservation
from app.infrastructure.db.models.vendor_scrape_target import VendorScrapeTarget

OWN_TABLES = frozenset({VendorScrapeTarget.__tablename__, VendorPriceObservation.__tablename__})

__all__ = ["Base", "OWN_TABLES", "VERSION_TABLE", "VendorPriceObservation", "VendorScrapeTarget"]
