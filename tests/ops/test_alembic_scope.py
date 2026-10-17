"""Alembic covers this service's own two tables and nothing the platform owns (no Docker needed)."""

import re
from pathlib import Path

from app.infrastructure.db.models import OWN_TABLES, VERSION_TABLE

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_TABLES = {"peptides", "peptide_graph", "benefits", "side_effects", "administration_methods"}


def test_scope_and_version_table():
    assert OWN_TABLES == {"vendor_scrape_targets", "vendor_price_observations"}
    assert VERSION_TABLE == "alembic_version_web_scrape"


def test_revisions_never_name_a_platform_table():
    for path in (ROOT / "alembic" / "versions").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        created = set(re.findall(r"(?:CREATE|ALTER) TABLE (?:IF NOT EXISTS )?([a-z_]+)", text, re.I))
        assert created <= OWN_TABLES, f"{path.name} touches {created - OWN_TABLES}"
        assert not (PLATFORM_TABLES & created)


def test_startup_migration_is_off_by_default(monkeypatch):
    monkeypatch.delenv("VENDOR_SCHEMA_AUTO_CREATE", raising=False)
    from app.core.config import Settings

    assert Settings(_env_file=None).VENDOR_SCHEMA_AUTO_CREATE is False
