# XR-8 consumer — see orchestrator/docs/ecosystem/dependencies.md#xr-8
"""Contract test: every platform table web_scrape reads, writes or deletes from
must exist in the platform's Drizzle schema (peptides-platform owns it).

web_scrape talks to the platform database with raw SQL, so a Drizzle rename
or drop breaks it silently. This test parses the platform schema files
(``apps/api/src/**/db/schema/**/*.ts``) from a local checkout and compares.

Where the platform columns come from:

* a peptides-platform checkout (``PLATFORM_SCHEMA_REPO``, default the workspace
  checkout) when present: the live Drizzle files, and the vendored snapshot must
  match it, so a stale snapshot fails here;
* otherwise the vendored snapshot ``contracts/platform-schema/<date>.json`` (what
  CI uses). Regenerate it with ``scripts/export_platform_schema.py``.
"""

from __future__ import annotations

import re

import pytest

from tests.sync.platform_schema import (
    OWN_TABLES,
    PLATFORM_REPO,
    ROOT,
    cascade_tables,
    latest_snapshot_path,
    load_snapshot,
    parse_drizzle_schema,
    sql_tables,
    tables_in_use,
    written_columns,
)

# Columns web_scrape writes that the platform's Drizzle schema does not declare.
# Empty since platform Drizzle 0138 (webscrape-1) declared the last four
# (peptides.activity_type, molecular_type, molecular_length, molecular_weight),
# which hand-run SQL in this repo's old migrations/ folder used to add. Keep it
# empty: an entry is a cross-repo bug to fix in the platform schema first (XR-8,
# https://github.com/peptides-apps/peptides-platform/issues/522, ADR 0009).
KNOWN_UNDECLARED_COLUMNS: set[tuple[str, str]] = set()


@pytest.fixture(scope="module")
def platform() -> dict[str, set[str]]:
    if (PLATFORM_REPO / "apps" / "api" / "src").is_dir():
        tables = parse_drizzle_schema()
        assert "peptides" in tables, "parser found no peptides table; has the schema layout moved?"
        return tables
    tables, _ = load_snapshot()
    return tables


def test_parsers_see_the_tables_web_scrape_is_known_to_use():
    # Guards the source parsing itself, so a refactor cannot make the contract vacuous.
    assert {"peptides", "peptide_graph", "peptide_protocols"} <= sql_tables()
    assert {"peptide_benefits", "administration_methods", "citations"} <= set(written_columns())
    assert len(cascade_tables()) >= 20


def test_every_table_in_delete_peptide_cascading_exists_in_the_platform(platform):
    missing = [t for t in cascade_tables() if t not in platform]
    assert not missing, f"delete_peptide_cascading names tables the platform schema lacks: {missing}"


def test_every_platform_table_web_scrape_queries_exists(platform):
    used = (sql_tables() | set(written_columns())) - OWN_TABLES
    missing = sorted(t for t in used if t not in platform)
    assert not missing, f"web_scrape SQL names tables the platform schema lacks: {missing}"


def test_every_column_web_scrape_inserts_exists_in_the_platform(platform):
    undeclared = {
        (table, col)
        for table, cols in written_columns().items()
        if table in platform
        for col in cols
        if col not in platform[table]
    }
    unexpected = sorted(undeclared - KNOWN_UNDECLARED_COLUMNS)
    assert not unexpected, f"web_scrape inserts columns the platform schema lacks: {unexpected}"
    fixed = sorted(KNOWN_UNDECLARED_COLUMNS - undeclared)
    assert not fixed, f"now declared by the platform; remove from KNOWN_UNDECLARED_COLUMNS: {fixed}"


def test_snapshot_exists_and_covers_every_table_in_use():
    assert latest_snapshot_path() is not None, (
        "no contracts/platform-schema/*.json; run scripts/export_platform_schema.py"
    )
    snapshot, _ = load_snapshot()
    missing = sorted(tables_in_use() - set(snapshot))
    assert not missing, f"snapshot lacks tables this service uses: {missing}; regenerate it"


def test_snapshot_matches_the_platform_checkout_when_one_is_present():
    if not (PLATFORM_REPO / "apps" / "api" / "src").is_dir():
        pytest.skip("no platform checkout; the snapshot is the source of truth here")
    snapshot, meta = load_snapshot()
    live = parse_drizzle_schema()
    stale = sorted(t for t in snapshot if snapshot[t] != live.get(t))
    assert not stale, (
        f"snapshot (generated {meta.get('generated_at')}) differs from the platform checkout for {stale}; "
        "run scripts/export_platform_schema.py and commit"
    )


def test_the_peptides_columns_web_scrape_writes_are_declared_by_the_platform(platform):
    """webscrape-1: the four columns that hand-run SQL here used to add are platform
    Drizzle columns now (migration 0138). web_scrape writes them; it never creates them."""
    assert {"activity_type", "molecular_type", "molecular_length", "molecular_weight"} <= platform["peptides"]


def test_this_repo_holds_no_sql_that_changes_a_platform_table():
    """webscrape-1: the platform owns its schema. No migrations/ folder, and no SQL file
    here alters or creates a platform table; only Alembic's own two tables change here."""
    assert not (ROOT / "migrations").exists(), "platform SQL belongs in a peptides-platform Drizzle migration"
    ddl = re.compile(r"\b(?:ALTER|CREATE|DROP)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?\"?(\w+)", re.I)
    tops = [p for p in ROOT.iterdir() if not p.name.startswith(".") and p.name not in {"node_modules", "venv"}]
    sql_files = [p for top in tops for p in ([top] if top.is_file() else top.rglob("*.sql")) if p.suffix == ".sql"]
    offenders = []
    for sql_file in sql_files:
        tables = set(ddl.findall(sql_file.read_text(encoding="utf-8", errors="ignore"))) - OWN_TABLES
        if tables:
            offenders.append(f"{sql_file.relative_to(ROOT).as_posix()}: {sorted(tables)}")
    assert not offenders, f"SQL changing platform tables: {offenders}"
