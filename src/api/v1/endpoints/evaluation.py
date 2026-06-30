from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import os

from src.evaluation.runner import run_evaluation
from src.evaluation.graph_evaluator import run_graph_evaluation
from src.config import ENHANCED_CSV, GRAPH_CSV, log_debug, log_error
from src.core.job_queue import get_job_queue

router = APIRouter()

class EvaluationRequest(BaseModel):
    """
    Request body for triggering a sync-quality evaluation.

    - `limit` restricts how many peptides from the CSV are checked.
    - `output_json` optionally writes the full report to a JSON file on the server.
    """
    limit: Optional[int] = Field(
        None,
        description="Number of peptides (CSV rows) to evaluate. `null` means all available.",
        ge=1,
        examples=[None, 10, 50, 100],
    )
    output_json: Optional[str] = Field(
        None,
        description="Optional server-side file path to write the full evaluation report as JSON. "
                    "If `null`, results are only returned in the job result on retrieval.",
        examples=[None, "/tmp/core_eval_report.json", "/tmp/graph_eval_report.json"],
    )

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v < 1:
            raise ValueError("limit must be a positive integer (≥1) if provided.")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"limit": 10, "output_json": None},
                {"limit": 50, "output_json": "/tmp/eval_report.json"},
                {"limit": None, "output_json": None},
            ]
        }
    }


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


@router.post("/core", status_code=202)
async def start_core_evaluation(request: EvaluationRequest, background_tasks: BackgroundTasks):
    """
    📊 Evaluate **core database sync** quality.

    Compares CSV scraped data against PostgreSQL for **13 checks per peptide**:

    | # | Check | Description |
    |---|-------|-------------|
    | 1 | `peptide_exists` | Peptide row present in `peptides` table |
    | 2 | `core_fields_match` | Name, slug, formula, MW, etc. match CSV |
    | 3 | `benefits_match` | Listed benefits match |
    | 4 | `side_effects_match` | Side effects match |
    | 5 | `dosages_match` | Dosage info matches |
    | 6 | `schedules_match` | Administration schedules match |
    | 7 | `admin_methods_match` | Administration methods match |
    | 8 | `interactions_match` | Drug—drug interactions match |
    | 9 | `indications_match` | Medical indications match |
    | 10 | `protocols_match` | Research protocols match |
    | 11 | `references_match` | Cited references match |
    | 12 | `missing_columns` | Columns in CSV absent from DB |
    | 13 | `extra_columns` | Columns in DB absent from CSV |

    ### Responses
    - **202** → Accepted. Returns a `job_id` — poll `/api/v1/operations/job/{job_id}` for results.
    - **422** → Validation error (invalid `limit`).
    - **500** → `DATABASE_URL` not configured or missing master CSV.

    ### Example
    ```json
    {"limit": 10, "output_json": null}
    ```
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")

    csv_path = str(ENHANCED_CSV)
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=500, detail=f"Enhanced CSV not found at {csv_path}. Run a core sync first.")

    queue = get_job_queue()
    job = queue.create_job("/evaluation/core", {"limit": request.limit, "output_json": request.output_json})
    background_tasks.add_task(run_core_evaluation_task, job.job_id, request.limit, request.output_json, db_url, csv_path)

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


@router.post("/graph", status_code=202)
async def start_graph_evaluation(request: EvaluationRequest, background_tasks: BackgroundTasks):
    """
    📊 Evaluate **graph data sync** quality.

    Compares CSV scraped data against `peptide_graph` table for **5 checks per peptide**:

    | # | Check | What it verifies |
    |---|-------|------------------|
    | 1 | `graph_rows_exist` | At least one row in `peptide_graph` for this peptide |
    | 2 | `time_range_coverage` | Every expected `time_range` value has a DB row |
    | 3 | `path_data_populated` | `svg_path` column is non-empty (valid SVG path string) |
    | 4 | `points_populated` | Coordinate points JSON array is non-empty |
    | 5 | `markers_populated` | Marker data JSON array is non-empty |

    ### Responses
    - **202** → Accepted. Returns a `job_id` for tracking.
    - **422** → Validation error.
    - **500** → `DATABASE_URL` not configured or missing master CSV.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured.")

    csv_path = str(GRAPH_CSV)
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=500, detail=f"Graph CSV not found at {csv_path}. Run a graph sync first.")

    queue = get_job_queue()
    job = queue.create_job("/evaluation/graph", {"limit": request.limit, "output_json": request.output_json})
    background_tasks.add_task(run_graph_evaluation_task, job.job_id, request.limit, request.output_json, db_url, csv_path)

    return job.to_dict()

