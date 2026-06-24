from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os

from src.evaluation.runner import run_evaluation
from src.config import MASTER_CSV, log_debug, log_error
from src.core.job_queue import get_job_queue

router = APIRouter()

class EvaluationRequest(BaseModel):
    limit: Optional[int] = None
    output_json: Optional[str] = None


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
    """Evaluate core database sync (CSV expected vs DB actual). Returns job_id for tracking."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")
    
    csv_path = str(MASTER_CSV)
    queue = get_job_queue()
    job = queue.create_job("/evaluation/core", {"limit": request.limit, "output_json": request.output_json})
    background_tasks.add_task(run_core_evaluation_task, job.job_id, request.limit, request.output_json, db_url, csv_path)
    
    return job.to_dict()

@router.post("/graph")
async def start_graph_evaluation(request: EvaluationRequest, background_tasks: BackgroundTasks):
    """
    To be fully implemented natively as Graph Evaluation is required.
    For now, return a placeholder as the evaluation pipeline is focused on core mappings.
    """
    return {"message": "Graph Database Evaluation pipeline isolated. Feature pending full evaluation mapping."}
