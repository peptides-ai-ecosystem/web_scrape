from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os

from src.evaluation.runner import run_evaluation
from src.evaluation.graph_evaluator import run_graph_evaluation
from src.config import MASTER_CSV, log_debug, log_error
from src.core.job_queue import get_job_queue

router = APIRouter()

class EvaluationRequest(BaseModel):
    limit: Optional[int] = None
    output_json: Optional[str] = None


# ---------------------------------------------------------------------------
# Core Evaluation
# ---------------------------------------------------------------------------

def run_core_evaluation_task(job_id: str, limit: Optional[int], output_json: Optional[str], db_url: str, csv_path: str):
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return
    
    job.start()
    try:
        run_evaluation(db_url, csv_path, limit=limit, output_json=output_json)
        job.complete({
            "limit": limit,
            "output_file": output_json
        })
    except Exception as e:
        log_error(f"Fatal error during core evaluation task: {e}", "evaluation_endpoint")
        job.fail(str(e))


@router.post("/core")
async def start_core_evaluation(request: EvaluationRequest, background_tasks: BackgroundTasks):
    """
    Evaluate core database sync (CSV expected vs DB actual).

    Runs 13 checks per peptide covering existence, core fields, benefits,
    side effects, dosages, schedules, administration methods, interactions,
    indications, protocols, and references.

    Returns a job_id for tracking via `/operations/job/{job_id}`.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")
    
    csv_path = str(MASTER_CSV)
    queue = get_job_queue()
    job = queue.create_job("/evaluation/core", {"limit": request.limit, "output_json": request.output_json})
    background_tasks.add_task(run_core_evaluation_task, job.job_id, request.limit, request.output_json, db_url, csv_path)
    
    return job.to_dict()


# ---------------------------------------------------------------------------
# Graph Evaluation
# ---------------------------------------------------------------------------

def run_graph_evaluation_task(job_id: str, limit: Optional[int], output_json: Optional[str], db_url: str, csv_path: str):
    """
    Background task: evaluate graph data in peptide_graph vs what the CSV expects.
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)
    if not job:
        return

    job.start()
    try:
        run_graph_evaluation(db_url, csv_path, limit=limit, output_json=output_json)
        job.complete({
            "limit": limit,
            "output_file": output_json,
        })
    except Exception as e:
        log_error(f"Fatal error during graph evaluation task: {e}", "evaluation_endpoint")
        job.fail(str(e))


@router.post("/graph")
async def start_graph_evaluation(request: EvaluationRequest, background_tasks: BackgroundTasks):
    """
    Evaluate graph data sync (CSV expected vs peptide_graph DB table).

    Runs 5 checks per peptide:
    - **graph_rows_exist** — any rows in `peptide_graph`
    - **time_range_coverage** — each expected time_range is in DB
    - **path_data_populated** — SVG path string is non-empty
    - **points_populated** — coordinate points array is non-empty
    - **markers_populated** — marker data array is non-empty

    Returns a job_id for tracking via `/operations/job/{job_id}`.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")

    csv_path = str(MASTER_CSV)
    queue = get_job_queue()
    job = queue.create_job("/evaluation/graph", {"limit": request.limit, "output_json": request.output_json})
    background_tasks.add_task(run_graph_evaluation_task, job.job_id, request.limit, request.output_json, db_url, csv_path)

    return job.to_dict()

