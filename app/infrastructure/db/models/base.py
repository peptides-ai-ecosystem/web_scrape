"""Declarative base and the Alembic version table name for web_scrape's own tables."""
from sqlalchemy.orm import DeclarativeBase

# One version table per service in the shared database; never alembic_version.
VERSION_TABLE = "alembic_version_web_scrape"


class Base(DeclarativeBase):
    pass
