"""Create the competitor-scraping tables on startup (CEO round 2, P2).

This service has no migration runner — its schema changes ship as idempotent
``migration_*.sql`` files applied by hand. The two competitor tables are the
exception: the admin "Scrape" tab calls straight into them, so a box whose
operator never ran the SQL would answer every call with a 500. Both files are
pure ``CREATE ... IF NOT EXISTS``, so applying them on every boot is safe.

Opt out with ``VENDOR_SCHEMA_AUTO_CREATE=false`` where the DB role has no DDL
rights; the service then assumes the operator applied the files.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[3]

VENDOR_SCHEMA_FILES: List[Path] = [
    _ROOT / "migration_vendor_price_observations.sql",
    _ROOT / "migration_vendor_scrape_targets.sql",
]


def ensure_vendor_schema(db_url: str) -> bool:
    """Apply the competitor-scraping DDL. Never raises; returns success."""
    if not db_url:
        return False
    try:
        import psycopg2

        conn = psycopg2.connect(db_url, connect_timeout=5)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vendor schema bootstrap skipped — cannot connect: %s", exc)
        return False
    try:
        with conn, conn.cursor() as cur:
            for path in VENDOR_SCHEMA_FILES:
                cur.execute(path.read_text(encoding="utf-8"))
        logger.info("Vendor scraping tables present (vendor_price_observations, vendor_scrape_targets).")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Vendor schema bootstrap failed: %s", exc)
        return False
    finally:
        conn.close()
