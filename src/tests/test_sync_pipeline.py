"""
test_sync_pipeline.py
=====================
End-to-end pipeline test: sync CSV data → DB → evaluate → verify.

Usage:
    # Fast mode: sync existing CSV to DB, evaluate, query DB (no scraping)
    uv run python -m src.tests.test_sync_pipeline --limit 2

    # Full mode: scrape web + sync + evaluate + DB query
    uv run python -m src.tests.test_sync_pipeline --scrape --limit 2

    # Specify custom CSV
    uv run python -m src.tests.test_sync_pipeline --csv output_dir/pep_pedia_enhanced.csv --limit 3

    # Run all 4 rows
    uv run python -m src.tests.test_sync_pipeline --limit 4
"""

import argparse
import csv
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from src.config import DATABASE_URL, ENHANCED_CSV, GRAPH_CSV, OUTPUT_DIR
from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.mappers.graph_import_orchestrator import GraphImportOrchestrator
from src.evaluation.runner import run_evaluation as run_core_evaluation
from src.evaluation.graph_evaluator import run_graph_evaluation
from src.infrastructure.db import DbManager
from src.infrastructure.csv_storage import CSVStorage
from src.utils.error_tracker import ErrorTracker


# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — Helpers
# ═════════════════════════════════════════════════════════════════════════════

def print_header(title: str):
    """Print a section header."""
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


def print_step(step: int, total: int, label: str):
    """Print a step indicator."""
    print(f"\n─── [Step {step}/{total}] {label} ───")


def read_csv_rows(csv_path: str, limit: Optional[int]) -> List[Dict[str, Any]]:
    """Read CSV rows up to the given limit."""
    if not os.path.exists(csv_path):
        print(f"  [ERROR] CSV not found: {csv_path}")
        return []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(row)
            if limit and len(rows) >= limit:
                break
    print(f"  → Read {len(rows)} row(s) from {Path(csv_path).name}")
    for r in rows:
        print(f"    • {r.get('Peptide_Name', '?'):20s} | Method: {r.get('Method', '?'):15s}")
    return rows


def query_db_table(db: DbManager, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Run a query and return results as list of dicts."""
    conn = db.connect()
    if conn is None or conn.closed:
        print("    [ERROR] Cannot connect to DB")
        return []
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return []
        rows = cur.fetchall()
        if not rows:
            return []
        if hasattr(rows[0], 'keys'):
            return [dict(r) for r in rows]
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]


# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — Core Pipeline Steps
# ═════════════════════════════════════════════════════════════════════════════

def step_sync_core(db_url: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Step 2: Sync CSV rows to core DB tables."""
    print_header("STEP 2: Core DB Sync")
    orchestrator = DbImportOrchestrator()
    tracker = ErrorTracker()
    result = orchestrator.sync_to_db(db_url, rows, tracker=tracker)
    if tracker.has_errors():
        tracker.print_summary()
    return result


def step_sync_graph(db_url: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Step 3: Sync graph data to DB."""
    print_header("STEP 3: Graph DB Sync")
    orchestrator = GraphImportOrchestrator()
    tracker = ErrorTracker()
    result = orchestrator.sync_graph_data(db_url, rows, tracker=tracker, action_type="manual")
    if tracker.has_errors():
        tracker.print_summary()
    return result


def step_evaluate_core(db_url: str, csv_path: str, limit: Optional[int]):
    """Step 4: Evaluate core sync quality."""
    print_header("STEP 4: Core Sync Evaluation")
    result = run_core_evaluation(db_url, csv_path, limit=limit)
    print(f"\n  Evaluation result:")
    print(f"    Total rows      : {result.get('total', 0)}")
    print(f"    Evaluated       : {result.get('evaluated_count', 0)}")
    print(f"    Skipped         : {result.get('skipped_count', 0)}")
    return result


def step_evaluate_graph(db_url: str, csv_path: str, limit: Optional[int]):
    """Step 5: Evaluate graph sync quality."""
    print_header("STEP 5: Graph Sync Evaluation")
    result = run_graph_evaluation(db_url, csv_path, limit=limit)
    print(f"\n  Evaluation result:")
    print(f"    Total rows      : {result.get('total', 0)}")
    print(f"    Evaluated       : {result.get('evaluated_count', 0)}")
    print(f"    Skipped         : {result.get('skipped_count', 0)}")
    return result


def step_query_db(db_url: str, limit: int):
    """Step 6: Query DB directly to verify inserted data."""
    print_header("STEP 6: Direct DB Verification")

    db = DbManager(db_url)
    try:
        # ── 6a: Peptides table ──────────────────────────────────────────
        print("\n  ─── 6a. Peptides in DB (last synced) ───")
        peptides = query_db_table(db,
            "SELECT id, name, slug, overview, fda_approval_status, wada_status "
            "FROM peptides ORDER BY id DESC LIMIT %s", (limit * 2,)
        )
        if not peptides:
            print("    [No peptides found]")
        else:
            for p in peptides:
                overview_short = (p.get("overview") or "")[:60]
                print(f"    #{p['id']:<4} {p['name']:<20s} slug={p['slug']:<25s}")
                if overview_short:
                    print(f"         overview: {overview_short}...")

        # ── 6b: Administration methods ──────────────────────────────────
        print("\n  ─── 6b. Administration Methods ───")
        methods = query_db_table(db,
            "SELECT id, name FROM administration_methods ORDER BY id"
        )
        for m in methods:
            print(f"    #{m['id']} {m['name']}")

        # ── 6c: Benefits linked to recently synced peptides ────────────
        print("\n  ─── 6c. Benefits per Peptide ───")
        for p in peptides[:limit]:
            pid = p["id"]
            benefits = query_db_table(db,
                "SELECT b.name FROM benefits b "
                "JOIN peptide_benefits pb ON pb.benefit_id = b.id "
                "WHERE pb.peptide_id = %s", (pid,)
            )
            names = [b["name"] for b in benefits]
            print(f"    {p['name']:<20s} → {', '.join(names) if names else '(none)'}")

        # ── 6d: Side effects per peptide ────────────────────────────────
        print("\n  ─── 6d. Side Effects per Peptide ───")
        for p in peptides[:limit]:
            pid = p["id"]
            effects = query_db_table(db,
                "SELECT se.name FROM side_effects se "
                "JOIN peptide_side_effects pse ON pse.side_effect_id = se.id "
                "WHERE pse.peptide_id = %s", (pid,)
            )
            names = [e["name"] for e in effects]
            print(f"    {p['name']:<20s} → {', '.join(names) if names else '(none)'}")

        # ── 6e: Protocols per peptide ───────────────────────────────────
        print("\n  ─── 6e. Protocols per Peptide ───")
        for p in peptides[:limit]:
            pid = p["id"]
            protocols = query_db_table(db,
                "SELECT pp.id, pp.name, am.name AS method FROM peptide_protocols pp "
                "LEFT JOIN administration_methods am ON am.id = pp.administration_method_id "
                "WHERE pp.peptide_id = %s AND pp.deleted_at IS NULL", (pid,)
            )
            for proto in protocols:
                print(f"    {p['name']:<20s} → Protocol #{proto['id']}: {proto['name'] or '(unnamed)'} [{proto['method']}]")

        # ── 6f: Dosages via protocols ───────────────────────────────────
        print("\n  ─── 6f. Dosages per Peptide ───")
        for p in peptides[:limit]:
            pid = p["id"]
            dosages = query_db_table(db,
                "SELECT DISTINCT d.amount, d.unit FROM dosages d "
                "JOIN protocol_dosages pd ON pd.dosage_id = d.id "
                "JOIN peptide_protocols pp ON pp.id = pd.protocol_id "
                "WHERE pp.peptide_id = %s", (pid,)
            )
            dose_strs = [f"{d['amount']} {d['unit'] or ''}".strip() for d in dosages]
            print(f"    {p['name']:<20s} → {', '.join(dose_strs) if dose_strs else '(none)'}")

        # ── 6g: Schedules per peptide ───────────────────────────────────
        print("\n  ─── 6g. Schedules per Peptide ───")
        for p in peptides[:limit]:
            pid = p["id"]
            schedules = query_db_table(db,
                "SELECT DISTINCT s.name FROM schedules s "
                "JOIN protocol_dosages pd ON pd.schedule_id = s.id "
                "JOIN peptide_protocols pp ON pp.id = pd.protocol_id "
                "WHERE pp.peptide_id = %s", (pid,)
            )
            names = [s["name"] for s in schedules]
            print(f"    {p['name']:<20s} → {', '.join(names) if names else '(none)'}")

        # ── 6h: Interactions ────────────────────────────────────────────
        print("\n  ─── 6h. Interactions per Peptide ───")
        for p in peptides[:limit]:
            pid = p["id"]
            interactions = query_db_table(db,
                "SELECT peptide_name_2, interaction_type FROM peptide_interactions "
                "WHERE peptide_id_1 = %s", (pid,)
            )
            for inter in interactions:
                print(f"    {p['name']:<20s} → {inter.get('peptide_name_2','?')} ({inter.get('interaction_type','?')})")

        # ── 6i: Indications ─────────────────────────────────────────────
        print("\n  ─── 6i. Indications per Peptide ───")
        for p in peptides[:limit]:
            pid = p["id"]
            indications = query_db_table(db,
                "SELECT indication_title, effectiveness_tag FROM peptide_research_indications "
                "WHERE peptide_id = %s", (pid,)
            )
            for ind in indications:
                print(f"    {p['name']:<20s} → {ind.get('indication_title','?'):40s} [{ind.get('effectiveness_tag','?')}]")

        # ── 6j: Graph data ──────────────────────────────────────────────
        print("\n  ─── 6j. Graph Data (peptide_graph) ───")
        for p in peptides[:limit]:
            pid = p["id"]
            graph_rows = query_db_table(db,
                "SELECT pg.id, am.name AS method_name, pg.time_range, "
                "       pg.path_data IS NOT NULL AS has_path, "
                "       pg.points IS NOT NULL AS has_points, "
                "       pg.markers IS NOT NULL AS has_markers "
                "FROM peptide_graph pg "
                "JOIN administration_methods am ON am.id = pg.administration_method_id "
                "WHERE pg.peptide_id = %s LIMIT 5", (pid,)
            )
            if graph_rows:
                for g in graph_rows:
                    print(f"    {p['name']:<20s} → method={g['method_name']:<15s} time={g['time_range']:<5s} "
                          f"path={'✓' if g['has_path'] else '✗'} points={'✓' if g['has_points'] else '✗'} markers={'✓' if g['has_markers'] else '✗'}")
            else:
                print(f"    {p['name']:<20s} → (no graph data)")

        # ── 6k: Row counts summary ──────────────────────────────────────
        print("\n  ─── 6k. Summary Counts ───")
        counts = query_db_table(db, """
            SELECT 'peptides'           AS tbl, COUNT(*)::int AS cnt FROM peptides
            UNION ALL SELECT 'benefits',        COUNT(*)::int FROM benefits
            UNION ALL SELECT 'side_effects',     COUNT(*)::int FROM side_effects
            UNION ALL SELECT 'schedules',        COUNT(*)::int FROM schedules
            UNION ALL SELECT 'administration_methods', COUNT(*)::int FROM administration_methods
            UNION ALL SELECT 'dosages',          COUNT(*)::int FROM dosages
            UNION ALL SELECT 'peptide_protocols', COUNT(*)::int FROM peptide_protocols
            UNION ALL SELECT 'peptide_graph',     COUNT(*)::int FROM peptide_graph
            ORDER BY tbl
        """)
        for c in counts:
            print(f"    {c['tbl']:<30s} {c['cnt']:>6} rows")

    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — Main Orchestrator
# ═════════════════════════════════════════════════════════════════════════════

def run_pipeline(
    csv_path: str,
    graph_csv_path: str,
    limit: Optional[int],
    do_scrape: bool,
    db_url: str,
):
    """
    Run the full pipeline:
      1. (optional) Scrape web data using the scheduler's combined sync
      2. Read CSV
      3. Core DB sync
      4. Graph DB sync
      5. Core evaluation
      6. Graph evaluation
      7. Direct DB query verification
    """
    if do_scrape:
        total_steps = 7
    else:
        total_steps = 6
    step = 0

    # ── Setup ───────────────────────────────────────────────────────────────
    print_header("SYNC PIPELINE TEST")
    print(f"  DB URL      : {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print(f"  CSV         : {csv_path}")
    print(f"  Graph CSV   : {graph_csv_path}")
    print(f"  Limit       : {limit or 'unlimited'}")
    print(f"  Mode        : {'Full (scrape + sync)' if do_scrape else 'Fast (sync from existing CSV)'}")
    print(f"{'='*65}\n")

    # ── Step 1 (optional): Scrape + sync via scheduler ─────────────────────
    if do_scrape:
        step += 1
        print_step(step, total_steps, "Scrape web data & sync (scheduler)")
        print("  Calling run_combined_sync_job() — this will scrape the web...\n")
        from src.core.scheduler import run_combined_sync_job
        run_combined_sync_job(limit=limit)
        print("\n  [DONE] Scheduler sync completed.")
        # After scraping, re-read CSVs (they were overwritten)
        rows = read_csv_rows(csv_path, limit)
        graph_rows = read_csv_rows(graph_csv_path, limit)
    else:
        # ── Step 1 (fast path): Read CSV ───────────────────────────────────
        step += 1
        print_step(step, total_steps, "Read CSV data")
        rows = read_csv_rows(csv_path, limit)
        if not rows:
            print("  [ABORT] No data to process.")
            return
        graph_rows = read_csv_rows(graph_csv_path, limit)

    # ── Step 2: Core DB Sync ───────────────────────────────────────────────
    step += 1
    print_step(step, total_steps, "Sync to Core DB tables")
    sync_result = step_sync_core(db_url, rows)
    print(f"\n  Core sync result: {sync_result.get('synced_count', 0)} synced, "
          f"{sync_result.get('skipped_count', 0)} skipped")

    # ── Step 3: Graph DB Sync ──────────────────────────────────────────────
    step += 1
    print_step(step, total_steps, "Sync Graph data to DB")
    if graph_rows:
        graph_result = step_sync_graph(db_url, graph_rows)
        print(f"\n  Graph sync result: {graph_result.get('synced_count', 0)} synced, "
              f"{graph_result.get('skipped_count', 0)} skipped")
    else:
        print("\n  [SKIP] No graph CSV rows to sync.")

    # ── Step 4: Core Evaluation ────────────────────────────────────────────
    step += 1
    print_step(step, total_steps, "Evaluate Core sync")
    eval_result = step_evaluate_core(db_url, csv_path, limit)

    # ── Step 5: Graph Evaluation ───────────────────────────────────────────
    step += 1
    print_step(step, total_steps, "Evaluate Graph sync")
    if graph_rows:
        step_evaluate_graph(db_url, graph_csv_path, limit)
    else:
        print("\n  [SKIP] No graph CSV rows to evaluate.")

    # ── Step 6 (or 7): Direct DB Verification ──────────────────────────────
    step += 1
    print_step(step, total_steps, "Verify DB directly")
    effective_limit = limit or len(rows)
    step_query_db(db_url, min(effective_limit, 4))

    # ── Final Summary ──────────────────────────────────────────────────────
    print_header("PIPELINE COMPLETE")
    print(f"  CSV rows processed : {len(rows)}")
    print(f"  Core synced        : {sync_result.get('synced_count', 0)}")
    print(f"  Core skipped       : {sync_result.get('skipped_count', 0)}")
    print(f"  Evaluated          : {eval_result.get('evaluated_count', 0)}")
    print(f"  Evaluation skipped : {eval_result.get('skipped_count', 0)}")
    print(f"\n  {'✓' if eval_result.get('evaluated_count', 0) > 0 else '⚠'} "
          f"Check the evaluation results above for detailed pass/fail per check.")
    print(f"{'='*65}\n")


# ═════════════════════════════════════════════════════════════════════════════
#  Entry Point
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Test the full sync pipeline: CSV → DB sync → evaluation → DB verification.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--csv", default=str(ENHANCED_CSV),
        help=f"Path to the core CSV file (default: {ENHANCED_CSV})"
    )
    parser.add_argument(
        "--graph-csv", default=str(GRAPH_CSV),
        help=f"Path to the graph CSV file (default: {GRAPH_CSV})"
    )
    parser.add_argument(
        "--limit", type=int, default=2,
        help="Max rows to process (default: 2)"
    )
    parser.add_argument(
        "--url", default=None,
        help="PostgreSQL connection URL (overrides DATABASE_URL env var)"
    )
    parser.add_argument(
        "--scrape", action="store_true",
        help="Run full pipeline including web scraping (requires Selenium)"
    )
    parser.add_argument(
        "--no-graph", action="store_true",
        help="Skip graph sync and evaluation"
    )

    args = parser.parse_args()

    db_url = args.url or DATABASE_URL
    if not db_url:
        print("[FATAL] No DATABASE_URL found. Set it in .env or pass --url.")
        sys.exit(1)

    run_pipeline(
        csv_path=args.csv,
        graph_csv_path=args.graph_csv,
        limit=args.limit,
        do_scrape=args.scrape,
        db_url=db_url,
    )


if __name__ == "__main__":
    main()
