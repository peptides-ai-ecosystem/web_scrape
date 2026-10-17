"""Sync-quality evaluation jobs (``/api/v1/evaluation``).

Starting an evaluation creates a job in the in-memory queue and hands the
background work to ``schedule`` (the endpoint passes
``BackgroundTasks.add_task``). The checks themselves live in ``src/evaluation/``.
"""
import os
from typing import Any, Callable, Dict, Optional

from src.config import ENHANCED_CSV, GRAPH_CSV, log_error
from src.core.errors import ConfigurationError
from src.core.job_queue import get_job_queue
from src.evaluation.graph_evaluator import run_graph_evaluation
from src.evaluation.runner import run_evaluation

Schedule = Callable[..., Any]


# ---------------------------------------------------------------------------
# Core Evaluation
# ---------------------------------------------------------------------------

def run_core_evaluation_task(job_id: str, limit: Optional[int], output_json: Optional[str], db_url: str, csv_path: str):
    """Background task: run the 13-check core evaluation on ingested peptides."""
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    try:
        result = run_evaluation(db_url, csv_path, limit=limit, output_json=output_json) or {}
        job.complete({
            "limit": limit,
            "output_file": output_json,
            "total": result.get("total", 0),
            "evaluated_count": result.get("evaluated_count", 0),
            "skipped_count": result.get("skipped_count", 0),
            "evaluated_peptides": result.get("evaluated_peptides", []),
            "skipped_peptides": result.get("skipped_peptides", []),
        })
    except Exception as e:
        log_error(f"Fatal error during core evaluation task: {e}", "evaluation_endpoint")
        job.fail(str(e))


def start_core_evaluation(limit: Optional[int], output_json: Optional[str], schedule: Schedule) -> Dict[str, Any]:
    """Queue the 13-check core evaluation; 500 when the DB URL or the enhanced CSV is missing."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ConfigurationError("DATABASE_URL not configured.")

    csv_path = str(ENHANCED_CSV)
    if not os.path.exists(csv_path):
        raise ConfigurationError(f"Enhanced CSV not found at {csv_path}. Run a core sync first.")

    queue = get_job_queue()
    job = queue.create_job("/evaluation/core", {"limit": limit, "output_json": output_json})
    schedule(run_core_evaluation_task, job.job_id, limit, output_json, db_url, csv_path)

    return job.to_dict()


# ---------------------------------------------------------------------------
# Graph Evaluation
# ---------------------------------------------------------------------------

def run_graph_evaluation_task(job_id: str, limit: Optional[int], output_json: Optional[str], db_url: str, csv_path: str):
    """Background task: evaluate graph data in peptide_graph vs what the CSV expects."""
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    try:
        result = run_graph_evaluation(db_url, csv_path, limit=limit, output_json=output_json) or {}
        job.complete({
            "limit": limit,
            "output_file": output_json,
            "total": result.get("total", 0),
            "evaluated_count": result.get("evaluated_count", 0),
            "skipped_count": result.get("skipped_count", 0),
            "evaluated_peptides": result.get("evaluated_peptides", []),
            "skipped_peptides": result.get("skipped_peptides", []),
        })
    except Exception as e:
        log_error(f"Fatal error during graph evaluation task: {e}", "evaluation_endpoint")
        job.fail(str(e))


def start_graph_evaluation(limit: Optional[int], output_json: Optional[str], schedule: Schedule) -> Dict[str, Any]:
    """Queue the 5-check graph evaluation; 500 when the DB URL or the graph CSV is missing."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ConfigurationError("DATABASE_URL not configured.")

    csv_path = str(GRAPH_CSV)
    if not os.path.exists(csv_path):
        raise ConfigurationError(f"Graph CSV not found at {csv_path}. Run a graph sync first.")

    queue = get_job_queue()
    job = queue.create_job("/evaluation/graph", {"limit": limit, "output_json": output_json})
    schedule(run_graph_evaluation_task, job.job_id, limit, output_json, db_url, csv_path)

    return job.to_dict()
