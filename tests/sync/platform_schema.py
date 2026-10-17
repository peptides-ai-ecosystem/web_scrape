"""Parsers behind the platform-schema contract (XR-8) and its vendored snapshot.

Two halves: what web_scrape's code touches (``sql_tables``, ``written_columns``,
``cascade_tables``, read from ``app/``) and what the platform declares
(``parse_drizzle_schema``, read from a peptides-platform checkout).
``scripts/export_platform_schema.py`` uses both to write
``contracts/platform-schema/<date>.json``.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_REPO = Path(os.getenv("PLATFORM_SCHEMA_REPO", "G:/aultra/microservice/peptides-platform"))

# web_scrape's own tables (migrations/, created by vendor_schema.py); not platform tables.
OWN_TABLES = {"vendor_price_observations", "vendor_scrape_targets"}

TABLE_RE = re.compile(r"""(?:pgTable|\.table)\(\s*["']([a-z_0-9]+)["']""")
COLUMN_RE = re.compile(r"""\b[a-zA-Z]+\(\s*["']([a-z_0-9]+)["']""")
SQL_TABLE_RE = re.compile(r"""\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|FROM|JOIN)\s+"?([a-z_][a-z_0-9]*)\b""")
UPDATE_SET_RE = re.compile(r"""\bUPDATE\s+([a-z_][a-z_0-9]*)\s+SET\s+([^%]*?)\s+WHERE""", re.IGNORECASE)
CTE_RE = re.compile(r"""(?:\bWITH|,)\s+([a-z_][a-z_0-9]*)\s+AS\s*\(""", re.IGNORECASE)


def tables_in(sql: str) -> set[str]:
    """Table names in one SQL string, minus its CTE names."""
    return set(SQL_TABLE_RE.findall(sql)) - set(CTE_RE.findall(sql))


def parse_drizzle_schema(repo: Path | None = None) -> dict[str, set[str]]:
    """Table name -> column names, from every Drizzle schema file."""
    files = [
        p for p in ((repo or PLATFORM_REPO) / "apps" / "api" / "src").rglob("*.ts") if "db/schema/" in p.as_posix()
    ]
    tables: dict[str, set[str]] = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        starts = [(m.start(), m.group(1)) for m in TABLE_RE.finditer(text)]
        for i, (start, name) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
            tables.setdefault(name, set()).update(COLUMN_RE.findall(text[start:end]))
    return tables


def source_files() -> list[Path]:
    return [p for p in (ROOT / "app").rglob("*.py") if "tests" not in p.parts]


def sql_tables() -> set[str]:
    """Literal table names in SQL strings under app/ (outside tests)."""
    found: set[str] = set()
    for path in source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.update(tables_in(node.value))
            elif isinstance(node, ast.JoinedStr):
                literal = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
                found.update(tables_in(literal))
    return found


def written_columns() -> dict[str, set[str]]:
    """Table -> columns for every insert whose table and columns are literals:
    ``_insert_guarded(cur, "t", [cols])``, ``link_relation("t", "c1", x, "c2", y)``,
    ``insert_lookup("t", name, col=...)``, literal ``UPDATE t SET a = ...``
    statements, plus the peptides payload."""
    out: dict[str, set[str]] = {}
    for path in source_files():
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
    for path in source_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Literal "UPDATE t SET a = %s, b = NOW() WHERE ..." statements.
                for table, sets in UPDATE_SET_RE.findall(node.value.replace("%s", "?")):
                    cols = {c.split("=")[0].strip() for c in sets.split(",") if "=" in c}
                    out.setdefault(table, set()).update(c for c in cols if re.fullmatch(r"[a-z_0-9]+", c))
    from app.services.sync.group_b.peptide_mapper import PeptideMapper

    out.setdefault("peptides", set()).update(PeptideMapper().map({}).keys())
    return out


def cascade_tables() -> list[str]:
    source = (ROOT / "app/repositories/peptide.py").read_text(encoding="utf-8")
    body = source[source.index("def delete_peptide_cascading") :]
    nxt = re.search(r"\n    def ", body[1:])
    body = body[: nxt.start() + 1] if nxt else body
    return sorted(set(re.findall(r"DELETE FROM ([a-z_0-9]+)", body)))


SNAPSHOT_DIR = ROOT / "contracts" / "platform-schema"


def tables_in_use() -> set[str]:
    """Every platform table this service queries, writes or deletes from."""
    return (sql_tables() | set(written_columns()) | set(cascade_tables())) - OWN_TABLES


def latest_snapshot_path() -> Path | None:
    files = sorted(SNAPSHOT_DIR.glob("*.json"))
    return files[-1] if files else None


def load_snapshot(path: Path | None = None) -> tuple[dict[str, set[str]], dict]:
    """(table -> columns, metadata) from a vendored snapshot."""
    path = path or latest_snapshot_path()
    if path is None:
        raise FileNotFoundError(f"no snapshot under {SNAPSHOT_DIR}; run scripts/export_platform_schema.py")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {t: set(cols) for t, cols in data["tables"].items()}, data
