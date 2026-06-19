"""
Evaluation Runner
=================
Orchestrates the full evaluation pipeline:
  1. Read CSV rows
  2. Build expected payloads (mapper stack)
  3. Fetch actual DB state
  4. Compare and produce results
  5. Report to console / JSON
"""
import csv
import os
import re
from typing import Optional

from src.evaluation.csv_expectation_builder import CsvExpectationBuilder
from src.evaluation.db_actual_fetcher import DbActualFetcher
from src.evaluation.evaluation_engine import EvaluationEngine
from src.evaluation.reporter import EvaluationReporter
from src.infrastructure.db.service import DbManager
from src.utils.peptide_utils import find_best_match, extract_essence


def run_evaluation(
    db_url: str,
    csv_path: str,
    limit: Optional[int] = None,
    output_json: Optional[str] = None,
) -> None:
    """
    Main entry point for the evaluation step.

    Parameters
    ----------
    db_url      : PostgreSQL connection string
    csv_path    : Path to the master CSV file
    limit       : Process at most this many CSV rows (None = all)
    output_json : If set, write the full JSON report to this file path
    """
    print(f"\n{'='*60}")
    print("  CSV SYNC EVALUATION")
    print(f"{'='*60}")
    print(f"  CSV  : {csv_path}")
    print(f"  DB   : {db_url.split('@')[-1] if '@' in db_url else db_url}")
    if limit:
        print(f"  Limit: {limit} row(s)")
    print(f"{'='*60}\n")

    # ── Step 1: Read CSV ────────────────────────────────────────────────────
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        return

    rows = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    print(f"[EVAL] Read {len(rows)} row(s) from CSV")

    # ── Step 2-4: Build expected → fetch actual → compare ──────────────────
    builder  = CsvExpectationBuilder()
    fetcher  = DbActualFetcher(db_url)
    engine   = EvaluationEngine()
    reporter = EvaluationReporter()

    # Pre-fetch all existing peptide identifiers and their essences for matching
    db_manager = DbManager(db_url)
    try:
        db_identifiers = db_manager.get_all_peptide_identifiers()
        db_essences = {extract_essence(ident): ident for ident in db_identifiers}

        results = []
        skipped = 0

        for row in rows:
            raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()

            # Use robust matching to find the peptide in DB
            matched_identifier = find_best_match(raw_name, db_identifiers, db_essences)
            
            # Build expected payload (mirrors orchestrator filter logic)
            expected = builder.build(row)
            if expected is None:
                print(f"[EVAL] SKIP {raw_name!r} — administration method not mappable")
                skipped += 1
                continue

            # If we matched a different identifier, update the expected slug
            if matched_identifier:
                expected["slug"] = matched_identifier
            
            slug = expected["slug"]
            print(f"[EVAL] Checking {raw_name!r} (slug: {slug})")

            # Fetch actual DB state
            actual = fetcher.fetch(slug)

            # Compare
            result = engine.evaluate(expected, actual)
            results.append(result)

    finally:
        fetcher.close()
        db_manager.close()

    if skipped:
        print(f"\n[EVAL] Skipped {skipped} row(s) with unmappable methods")

    if not results:
        print("[EVAL] No peptides to evaluate.")
        return

    # ── Step 5: Report ──────────────────────────────────────────────────────
    reporter.print_console(results)

    if output_json:
        reporter.save_json(results, output_json)
