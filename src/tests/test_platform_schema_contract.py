# XR-8 consumer — see orchestrator/docs/ecosystem/dependencies.md#xr-8
"""Contract test: every platform table web_scrape reads, writes or deletes from
must exist in the platform's Drizzle schema (peptides-platform owns it).

web_scrape talks to the platform database with raw SQL, so a Drizzle rename
or drop breaks it silently. This test parses the platform schema files
(``apps/api/src/**/db/schema/**/*.ts``) from a local checkout and compares.

Skipped unless the checkout exists. Point ``PLATFORM_SCHEMA_REPO`` at it
(default: the canonical workspace checkout). Run it against the platform
branch you are about to deploy with (staging), not an old checkout.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_REPO = Path(os.getenv("PLATFORM_SCHEMA_REPO", "G:/aultra/microservice/peptides-platform"))

# web_scrape's own tables (migrations/, created by vendor_schema.py); not platform tables.
OWN_TABLES = {"vendor_price_observations", "vendor_scrape_targets"}

# Columns web_scrape writes that the platform's Drizzle schema does not declare.
# They exist in the database only because migrations/ adds them by hand. Each
# entry is a cross-repo bug to fix in the platform schema (XR-8); remove the
# entry when it is fixed and the test will hold the line.
KNOWN_UNDECLARED_COLUMNS = {
    ("peptides", "molecular_type"),
    ("peptides", "molecular_length"),
    ("peptides", "molecular_weight"),
    ("peptides", "activity_type"),
}

_TABLE_RE = re.compile(r"""(?:pgTable|\.table)\(\s*["']([a-z_0-9]+)["']""")
_COLUMN_RE = re.compile(r"""\b[a-zA-Z]+\(\s*["']([a-z_0-9]+)["']""")
_SQL_TABLE_RE = re.compile(r"""\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|FROM|JOIN)\s+"?([a-z_][a-z_0-9]*)\b""")
_UPDATE_SET_RE = re.compile(r"""\bUPDATE\s+([a-z_][a-z_0-9]*)\s+SET\s+([^%]*?)\s+WHERE""", re.IGNORECASE)
_CTE_RE = re.compile(r"""(?:\bWITH|,)\s+([a-z_][a-z_0-9]*)\s+AS\s*\(""", re.IGNORECASE)


def _tables_in(sql: str) -> set[str]:
    """Table names in one SQL string, minus its CTE names."""
    return set(_SQL_TABLE_RE.findall(sql)) - set(_CTE_RE.findall(sql))


def _platform_schema() -> dict[str, set[str]]:
    """Table name -> column names, from every Drizzle schema file."""
    files = [
        p for p in (PLATFORM_REPO / "apps" / "api" / "src").rglob("*.ts")
        if "db/schema/" in p.as_posix()
    ]
    tables: dict[str, set[str]] = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        starts = [(m.start(), m.group(1)) for m in _TABLE_RE.finditer(text)]
        for i, (start, name) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
            tables.setdefault(name, set()).update(_COLUMN_RE.findall(text[start:end]))
    return tables


def _source_files() -> list[Path]:
    return [p for p in (ROOT / "src").rglob("*.py") if "tests" not in p.parts]


def _sql_tables() -> set[str]:
    """Literal table names in SQL strings under src/ (outside tests)."""
    found: set[str] = set()
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.update(_tables_in(node.value))
            elif isinstance(node, ast.JoinedStr):
                literal = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
                found.update(_tables_in(literal))
    return found


def _written_columns() -> dict[str, set[str]]:
    """Table -> columns for every insert whose table and columns are literals:
    ``_insert_guarded(cur, "t", [cols])``, ``link_relation("t", "c1", x, "c2", y)``,
    ``insert_lookup("t", name, col=...)``, literal ``UPDATE t SET a = ...``
    statements, plus the peptides payload."""
    out: dict[str, set[str]] = {}
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            args, fn = node.args, node.func.attr
            lit = [a.value if isinstance(a, ast.Constant) else None for a in args]
            if fn == "_insert_guarded" and len(args) >= 3 and isinstance(lit[1], str) and isinstance(args[2], ast.List):
                cols = {e.value for e in args[2].elts if isinstance(e, ast.Constant)}
                out.setdefault(lit[1], set()).update(cols)
            elif fn == "link_relation" and len(args) == 5 and all(isinstance(lit[i], str) for i in (0, 1, 3)):
                out.setdefault(lit[0], set()).update({lit[1], lit[3]})
            elif fn == "insert_lookup" and args and isinstance(lit[0], str):
                out.setdefault(lit[0], set()).update({"name", *(k.arg for k in node.keywords if k.arg)})
    for path in _source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Literal "UPDATE t SET a = %s, b = NOW() WHERE ..." statements.
                for table, sets in _UPDATE_SET_RE.findall(node.value.replace("%s", "?")):
                    cols = {c.split("=")[0].strip() for c in sets.split(",") if "=" in c}
                    out.setdefault(table, set()).update(c for c in cols if re.fullmatch(r"[a-z_0-9]+", c))
    from src.mappers.group_b.peptide_mapper import PeptideMapper

    out.setdefault("peptides", set()).update(PeptideMapper().map({}).keys())
    return out


def _cascade_tables() -> list[str]:
    source = (ROOT / "src/infrastructure/db/repositories/peptide.py").read_text(encoding="utf-8")
    body = source[source.index("def delete_peptide_cascading"):]
    nxt = re.search(r"\n    def ", body[1:])
    body = body[: nxt.start() + 1] if nxt else body
    return sorted(set(re.findall(r"DELETE FROM ([a-z_0-9]+)", body)))


@pytest.fixture(scope="module")
def platform() -> dict[str, set[str]]:
    if not (PLATFORM_REPO / "apps" / "api" / "src").is_dir():
        pytest.skip(f"platform checkout not found at {PLATFORM_REPO}; set PLATFORM_SCHEMA_REPO")
    tables = _platform_schema()
    assert "peptides" in tables, "parser found no peptides table; has the schema layout moved?"
    return tables


def test_parsers_see_the_tables_web_scrape_is_known_to_use():
    # Guards the source parsing itself, so a refactor cannot make the contract vacuous.
    assert {"peptides", "peptide_graph", "peptide_protocols"} <= _sql_tables()
    assert {"peptide_benefits", "administration_methods", "citations"} <= set(_written_columns())
    assert len(_cascade_tables()) >= 20


def test_every_table_in_delete_peptide_cascading_exists_in_the_platform(platform):
    missing = [t for t in _cascade_tables() if t not in platform]
    assert not missing, f"delete_peptide_cascading names tables the platform schema lacks: {missing}"


def test_every_platform_table_web_scrape_queries_exists(platform):
    used = (_sql_tables() | set(_written_columns())) - OWN_TABLES
    missing = sorted(t for t in used if t not in platform)
    assert not missing, f"web_scrape SQL names tables the platform schema lacks: {missing}"


def test_every_column_web_scrape_inserts_exists_in_the_platform(platform):
    undeclared = {
        (table, col)
        for table, cols in _written_columns().items()
        if table in platform
        for col in cols
        if col not in platform[table]
    }
    unexpected = sorted(undeclared - KNOWN_UNDECLARED_COLUMNS)
    assert not unexpected, f"web_scrape inserts columns the platform schema lacks: {unexpected}"
    fixed = sorted(KNOWN_UNDECLARED_COLUMNS - undeclared)
    assert not fixed, f"now declared by the platform; remove from KNOWN_UNDECLARED_COLUMNS: {fixed}"
