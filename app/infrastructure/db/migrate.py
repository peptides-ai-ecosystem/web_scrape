"""Run ``alembic upgrade head`` for web_scrape's own tables, from the app.

Only called at startup and only when ``VENDOR_SCHEMA_AUTO_CREATE=true`` (the
setting is off by default, like peptide: the deploy runs ``alembic upgrade
head`` itself). It never raises: a failure is logged and the service still
boots, as the former boot-time SQL runner did.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[3]


def upgrade_to_head() -> bool:
    """Apply every pending revision. Returns True on success, False if it failed."""
    try:
        from alembic.config import Config

        from alembic import command

        cfg = Config(str(_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(_ROOT / "alembic"))
        # Keep the app's own logging: env.py skips fileConfig for this run.
        cfg.attributes["skip_logging"] = True
        command.upgrade(cfg, "head")
        logger.info("web_scrape Alembic revisions applied (alembic_version_web_scrape at head).")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Alembic upgrade at startup failed: %s", exc)
        return False
