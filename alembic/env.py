"""Alembic environment for web_scrape's own tables (decision R10).

Only ``vendor_scrape_targets`` and ``vendor_price_observations`` are managed
here, with the version table ``alembic_version_web_scrape``. The database is
the platform's (``DATABASE_URL``), so autogenerate is limited to OWN_TABLES:
it must never emit DDL for a platform table (XR-8) or another service's table.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings
from app.infrastructure.db.models import OWN_TABLES, VERSION_TABLE, Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_url)
# The app runs migrations at startup only behind VENDOR_SCHEMA_AUTO_CREATE and
# passes skip_logging so fileConfig does not replace the app's log handlers.
if config.config_file_name and not config.attributes.get("skip_logging"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Autogenerate sees this service's tables and nothing else in the database."""
    if type_ == "table":
        return name in OWN_TABLES
    table = getattr(obj, "table", None)
    if table is not None:
        return table.name in OWN_TABLES
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sqlalchemy_database_url,
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
        include_object=include_object,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=VERSION_TABLE,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
