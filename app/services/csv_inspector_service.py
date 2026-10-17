"""Read the scraped CSV for the Core Data Inspector (``/api/v1/csv/*``).

The enhanced CSV (``app.core.config.ENHANCED_CSV``) is wide (about 2,400 columns),
so this module:

- Loads it once and caches in memory keyed by mtime, refreshing on file change.
- Returns only non-empty cells per peptide row.
- Groups columns by prefix to keep payloads small and navigable.

A missing CSV or an unknown peptide raises ``NotFoundError`` (404).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
from threading import Lock
from typing import Any, Dict, List, Optional

from app.core.config import ENHANCED_CSV as MASTER_CSV
from app.core.errors import NotFoundError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Column grouping
# ---------------------------------------------------------------------------
# A given prefix in the regex below is matched left-to-right; the first match
# wins. The order matters — more specific prefixes come first.
_GROUP_RULES: List[tuple] = [
    ("identity",            re.compile(r"^(Peptide_Name|Full_Name|Method|URL)$")),
    ("graph",               re.compile(r"^graph_data_json$")),
    ("quick_guide",         re.compile(r"^(typical_dose|route|cycle|storage|how_to_administer|how_to_reconstitute|how_to_take|molecular_information)")),
    ("overview",            re.compile(r"^overview_")),
    ("indications",         re.compile(r"^research_indications_")),
    ("protocols",           re.compile(r"^research_protocols_")),
    ("interactions",        re.compile(r"^peptide_interactions_")),
    ("side_effects",        re.compile(r"^(side_effects_|what_to_)")),
    ("quality_indicators",  re.compile(r"^quality_indicators_")),
    ("references_studies",  re.compile(r"^references_research_studies")),
    ("references_citations",re.compile(r"^references_citations")),
]

_GROUP_ORDER = [name for name, _ in _GROUP_RULES] + ["other"]


def _classify(column: str) -> str:
    for name, pattern in _GROUP_RULES:
        if pattern.match(column):
            return name
    return "other"


# ---------------------------------------------------------------------------
# Cached CSV reader
# ---------------------------------------------------------------------------


_CACHE_LOCK = Lock()
_CACHE: Dict[str, Any] = {
    "mtime": None,
    "headers": [],
    "rows": [],
    "by_key": {},
}


def _slugify(value: str) -> str:
    """Coarse slug compatible with how peptides are referenced in the DB."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _load_csv_if_needed() -> Dict[str, Any]:
    """Lazy-load and cache the master CSV; reload when mtime changes."""
    csv_path = str(MASTER_CSV)
    if not os.path.exists(csv_path):
        raise NotFoundError(
            f"Master CSV not found at {csv_path}. "
            "Run POST /api/v1/sync/core (or /sync/graph) first to populate it."
        )

    mtime = os.path.getmtime(csv_path)
    with _CACHE_LOCK:
        if _CACHE["mtime"] == mtime and _CACHE["rows"]:
            return _CACHE

        rows: List[Dict[str, str]] = []
        with open(csv_path, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            for row in reader:
                rows.append(row)

        by_key: Dict[str, int] = {}
        for idx, row in enumerate(rows):
            name = (row.get("Peptide_Name") or "").strip()
            method = (row.get("Method") or "").strip()
            if not name:
                continue
            by_key[f"{name.lower()}::{method.lower()}"] = idx
            by_key.setdefault(name.lower(), idx)
            slug = _slugify(name)
            if slug:
                by_key.setdefault(slug, idx)

        _CACHE["mtime"] = mtime
        _CACHE["headers"] = headers
        _CACHE["rows"] = rows
        _CACHE["by_key"] = by_key
        logger.info(
            "CSV inspector cache refreshed: %d rows, %d columns from %s",
            len(rows), len(headers), csv_path,
        )
        return _CACHE


def _row_to_grouped(row: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """
    Convert a wide CSV row into a `{group: {column: value}}` map, dropping
    empty cells. The `graph` group is JSON-parsed when possible.
    """
    grouped: Dict[str, Dict[str, Any]] = {g: {} for g in _GROUP_ORDER}
    for col, raw in row.items():
        if col is None:
            continue
        if raw is None or str(raw).strip() == "":
            continue
        group = _classify(col)
        value: Any = raw
        if group == "graph" and col == "graph_data_json":
            try:
                value = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                value = raw
        grouped[group][col] = value
    return {g: v for g, v in grouped.items() if v}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_peptides(q: Optional[str] = None) -> List[Dict[str, str]]:
    """Distinct ``(name, method)`` rows in the CSV, optionally filtered by name substring."""
    cache = _load_csv_if_needed()
    rows = cache["rows"]
    out: List[Dict[str, str]] = []
    needle = (q or "").lower()
    seen = set()
    for row in rows:
        name = (row.get("Peptide_Name") or "").strip()
        if not name:
            continue
        if needle and needle not in name.lower():
            continue
        method = (row.get("Method") or "").strip()
        key = (name.lower(), method.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "name": name,
            "method": method,
            "url": (row.get("URL") or "").strip(),
            "slug": _slugify(name),
            "full_name": (row.get("Full_Name") or "").strip(),
        })
    out.sort(key=lambda r: (r["name"].lower(), r["method"].lower()))
    return out


def get_peptide(name: str, method: Optional[str] = None) -> Dict[str, Any]:
    """One CSV row with its non-empty cells grouped by entity; 404 when none matches."""
    cache = _load_csv_if_needed()
    by_key: Dict[str, int] = cache["by_key"]
    rows = cache["rows"]

    needle_name = name.strip().lower()
    needle_method = (method or "").strip().lower()
    candidates = []
    if needle_method:
        candidates.append(f"{needle_name}::{needle_method}")
    candidates.append(needle_name)
    candidates.append(_slugify(name))

    idx = next((by_key[k] for k in candidates if k and k in by_key), None)
    if idx is None:
        raise NotFoundError(
            f"No CSV row found for name='{name}'" + (f", method='{method}'" if method else "")
        )

    row = rows[idx]
    payload = {
        "name": (row.get("Peptide_Name") or "").strip(),
        "full_name": (row.get("Full_Name") or "").strip(),
        "method": (row.get("Method") or "").strip(),
        "url": (row.get("URL") or "").strip(),
        "slug": _slugify(row.get("Peptide_Name") or ""),
        "groups": _row_to_grouped(row),
    }
    return payload


def list_columns() -> Dict[str, Any]:
    """Every CSV header bucketed by entity group."""
    cache = _load_csv_if_needed()
    headers: List[str] = cache["headers"]
    groups: Dict[str, List[str]] = {g: [] for g in _GROUP_ORDER}
    for h in headers:
        groups[_classify(h)].append(h)
    return {
        "total": len(headers),
        "row_count": len(cache["rows"]),
        "groups": {k: v for k, v in groups.items() if v},
    }
