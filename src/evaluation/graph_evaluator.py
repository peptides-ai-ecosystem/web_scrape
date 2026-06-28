"""
GraphEvaluator
==============
Dedicated evaluation pipeline for graph data stored in `peptide_graph`.

Compares the *expected* graph entries (derived from CSV via GraphMapper) against
the *actual* rows in the `peptide_graph` table and produces structured results.

Checks per peptide
------------------
1. graph_rows_exist      – any rows at all in peptide_graph
2. time_range_coverage   – each expected time_range is present in DB
3. path_data_populated   – path_data is non-empty for each matched row
4. points_populated      – points JSON array is non-empty
5. markers_populated     – markers JSON array is non-empty
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.infrastructure.db.service import DbManager
from src.mappers.group_d.graph_mapper import GraphMapper
from src.utils.peptide_utils import find_best_match, extract_essence


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GraphCheckResult:
    """Outcome of a single graph evaluation check."""
    name: str
    status: str          # "PASS" | "FAIL" | "WARN" | "SKIP"
    expected: Any = None
    actual: Any = None
    detail: str = ""

    @property
    def icon(self) -> str:
        return {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "SKIP": "–"}.get(self.status, "?")


@dataclass
class GraphPeptideEvalResult:
    """All graph check results for one peptide."""
    peptide_name: str
    slug: str
    administration_method: str = ""
    checks: List[GraphCheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.status in ("PASS", "WARN", "SKIP") for c in self.checks)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def total(self) -> int:
        return len(self.checks)


# ---------------------------------------------------------------------------
# Fetcher helpers
# ---------------------------------------------------------------------------

def _fetch_graph_rows(db: DbManager, peptide_id: int) -> List[Dict[str, Any]]:
    """Return all peptide_graph rows for the given peptide_id."""
    conn = db.conn
    if conn is None or conn.closed:
        db.connect()
        conn = db.conn
    with conn.cursor() as cur:
        cur.execute(
            "SELECT time_range, path_data, points, markers "
            "FROM peptide_graph WHERE peptide_id = %s",
            (peptide_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return []
        if hasattr(rows[0], "keys"):
            return [dict(r) for r in rows]
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]


def _is_nonempty_json(value: Any) -> bool:
    """Return True if value is a non-empty JSON list/dict (or already parsed)."""
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    try:
        parsed = json.loads(value)
        return bool(parsed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class GraphEvaluator:
    """
    Runs graph-specific checks for each peptide in a CSV and returns
    a list of GraphPeptideEvalResult objects.
    """

    def __init__(self):
        self._graph_mapper = GraphMapper()

    def _evaluate_peptide(
        self,
        peptide_name: str,
        slug: str,
        expected_graph: List[Dict[str, Any]],
        actual_rows: List[Dict[str, Any]],
        method: str,
    ) -> GraphPeptideEvalResult:
        result = GraphPeptideEvalResult(
            peptide_name=peptide_name,
            slug=slug,
            administration_method=method,
        )

        # ── Check 1: any graph rows exist ──────────────────────────────────
        if not actual_rows:
            result.checks.append(GraphCheckResult(
                name="graph_rows_exist",
                status="FAIL" if expected_graph else "SKIP",
                expected=f"{len(expected_graph)} row(s)",
                actual="0 row(s)",
                detail="No graph rows found in peptide_graph table" if expected_graph
                       else "No graph data expected from CSV",
            ))
            return result  # all remaining checks are meaningless

        result.checks.append(GraphCheckResult(
            name="graph_rows_exist",
            status="PASS",
            expected=f"{len(expected_graph)} row(s)",
            actual=f"{len(actual_rows)} row(s)",
        ))

        # Index actual rows by time_range for O(1) lookup
        actual_by_tr: Dict[str, Dict] = {r["time_range"]: r for r in actual_rows}
        expected_ranges = [g["time_range"] for g in expected_graph]

        # ── Check 2: time_range coverage ──────────────────────────────────
        missing_tr = [tr for tr in expected_ranges if tr not in actual_by_tr]
        if not expected_ranges:
            result.checks.append(GraphCheckResult(
                name="time_range_coverage",
                status="SKIP",
                detail="No expected time_ranges from CSV",
            ))
        elif missing_tr:
            result.checks.append(GraphCheckResult(
                name="time_range_coverage",
                status="FAIL",
                expected=expected_ranges,
                actual=list(actual_by_tr.keys()),
                detail=f"Missing time_ranges: {missing_tr}",
            ))
        else:
            result.checks.append(GraphCheckResult(
                name="time_range_coverage",
                status="PASS",
                expected=expected_ranges,
                actual=list(actual_by_tr.keys()),
            ))

        # ── Checks 3-5: field quality for matched rows ─────────────────────
        matched_ranges = [tr for tr in expected_ranges if tr in actual_by_tr]
        if not matched_ranges:
            for check_name in ("path_data_populated", "points_populated", "markers_populated"):
                result.checks.append(GraphCheckResult(
                    name=check_name, status="SKIP",
                    detail="No matched time_ranges to evaluate",
                ))
            return result

        def _field_check(check_name: str, field_key: str) -> GraphCheckResult:
            empty = [tr for tr in matched_ranges
                     if not _is_nonempty_json(actual_by_tr[tr].get(field_key))
                        and not actual_by_tr[tr].get(field_key)]
            if not empty:
                return GraphCheckResult(
                    name=check_name, status="PASS",
                    expected=f"all {len(matched_ranges)} row(s) populated",
                    actual=f"{len(matched_ranges)} OK",
                )
            return GraphCheckResult(
                name=check_name, status="FAIL",
                expected="all rows populated",
                actual=f"{len(matched_ranges) - len(empty)} / {len(matched_ranges)} populated",
                detail=f"Empty in time_ranges: {empty}",
            )

        # path_data is plain TEXT, not JSON
        path_empty = [tr for tr in matched_ranges
                      if not actual_by_tr[tr].get("path_data")]
        if not path_empty:
            result.checks.append(GraphCheckResult(
                name="path_data_populated", status="PASS",
                expected=f"all {len(matched_ranges)} row(s) populated",
                actual=f"{len(matched_ranges)} OK",
            ))
        else:
            result.checks.append(GraphCheckResult(
                name="path_data_populated", status="FAIL",
                expected="all rows populated",
                actual=f"{len(matched_ranges) - len(path_empty)} / {len(matched_ranges)} populated",
                detail=f"Empty path_data in time_ranges: {path_empty}",
            ))

        result.checks.append(_field_check("points_populated", "points"))
        result.checks.append(_field_check("markers_populated", "markers"))

        return result


def run_graph_evaluation(
    db_url: str,
    csv_path: str,
    limit: Optional[int] = None,
    output_json: Optional[str] = None,
) -> dict:
    """
    Main entry point for graph evaluation.

    Parameters
    ----------
    db_url      : PostgreSQL connection string
    csv_path    : Path to the master CSV file
    limit       : Process at most this many CSV rows (None = all)
    output_json : If set, write the full JSON report to this file path

    Returns
    -------
    dict with keys: total, evaluated_count, skipped_count, evaluated_peptides, skipped_peptides
    """
    print(f"\n{'='*60}")
    print("  GRAPH DATA EVALUATION")
    print(f"{'='*60}")
    print(f"  CSV  : {csv_path}")
    print(f"  DB   : {db_url.split('@')[-1] if '@' in db_url else db_url}")
    if limit:
        print(f"  Limit: {limit} row(s)")
    print(f"{'='*60}\n")

    # ── Step 1: Read CSV ──────────────────────────────────────────────────
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        return {
            "total": 0,
            "evaluated_count": 0,
            "skipped_count": 0,
            "evaluated_peptides": [],
            "skipped_peptides": [f"CSV not found: {csv_path}"],
        }

    rows: List[Dict[str, Any]] = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    print(f"[GRAPH-EVAL] Read {len(rows)} row(s) from CSV")

    # ── Step 2: Set up graph mapper + DB ─────────────────────────────────
    graph_mapper = GraphMapper()
    evaluator = GraphEvaluator()
    db = DbManager(db_url)

    evaluated_peptides = []
    skipped_peptides = []

    try:
        db.connect()
        db_identifiers = db.get_all_peptide_identifiers()
        db_essences = {extract_essence(ident): ident for ident in db_identifiers}

        results: List[GraphPeptideEvalResult] = []

        for row in rows:
            raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()

            # Map expected graph entries
            expected_graph = graph_mapper.map(row)
            if not expected_graph:
                print(f"[GRAPH-EVAL] SKIP {raw_name!r} — no graph_data_json in CSV")
                skipped_peptides.append(f"{raw_name} (no graph_data_json in CSV)")
                continue

            method = expected_graph[0].get("method", "Injectable") if expected_graph else "Injectable"

            # Match peptide slug
            matched_slug = find_best_match(raw_name, db_identifiers, db_essences)
            if not matched_slug:
                print(f"[GRAPH-EVAL] SKIP {raw_name!r} — not found in DB")
                skipped_peptides.append(f"{raw_name} (not found in DB)")
                continue

            print(f"[GRAPH-EVAL] Checking {raw_name!r} (slug: {matched_slug})")

            # Fetch peptide record
            peptide_record = db.get_peptide_by_slug(matched_slug)
            if not peptide_record:
                skipped_peptides.append(f"{raw_name} (slug {matched_slug} not in peptides table)")
                continue

            peptide_id = peptide_record["id"]

            # Fetch actual graph rows
            actual_rows = _fetch_graph_rows(db, peptide_id)

            # Run checks
            result = evaluator._evaluate_peptide(
                peptide_name=raw_name,
                slug=matched_slug,
                expected_graph=expected_graph,
                actual_rows=actual_rows,
                method=method,
            )
            results.append(result)
            evaluated_peptides.append({"name": raw_name, "slug": matched_slug, "method": method})

    finally:
        db.close()

    if skipped_peptides:
        print(f"\n[GRAPH-EVAL] Skipped {len(skipped_peptides)} row(s)")

    if not results:
        print("[GRAPH-EVAL] No peptides to evaluate.")
        return {
            "total": len(rows),
            "evaluated_count": 0,
            "skipped_count": len(skipped_peptides),
            "evaluated_peptides": [],
            "skipped_peptides": skipped_peptides,
        }

    # ── Step 3: Report ────────────────────────────────────────────────────
    _print_graph_console(results)

    if output_json:
        _save_graph_json(results, output_json)

    return {
        "total": len(rows),
        "evaluated_count": len(results),
        "skipped_count": len(skipped_peptides),
        "evaluated_peptides": evaluated_peptides,
        "skipped_peptides": skipped_peptides,
    }


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def _print_graph_console(results: List[GraphPeptideEvalResult]) -> None:
    total_peptides = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total_peptides - passed

    print(f"\n{'='*60}")
    print("  GRAPH EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Peptides evaluated : {total_peptides}")
    print(f"  Passed             : {passed}")
    print(f"  Failed             : {failed}")
    print(f"{'='*60}")

    for r in results:
        status_icon = "✓" if r.passed else "✗"
        print(f"\n  [{status_icon}] {r.peptide_name}  (method: {r.administration_method})")
        for check in r.checks:
            detail_str = f"  → {check.detail}" if check.detail else ""
            print(f"       {check.icon} {check.name:<28} "
                  f"exp={check.expected!r:20}  act={check.actual!r}{detail_str}")


def _save_graph_json(results: List[GraphPeptideEvalResult], path: str) -> None:
    import json as _json

    def _serialise(r: GraphPeptideEvalResult) -> dict:
        return {
            "peptide_name": r.peptide_name,
            "slug": r.slug,
            "administration_method": r.administration_method,
            "passed": r.passed,
            "fail_count": r.fail_count,
            "pass_count": r.pass_count,
            "total_checks": r.total,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "expected": c.expected,
                    "actual": c.actual,
                    "detail": c.detail,
                }
                for c in r.checks
            ],
        }

    payload = [_serialise(r) for r in results]
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, indent=2, default=str)
    print(f"\n[GRAPH-EVAL] JSON report saved to: {path}")
