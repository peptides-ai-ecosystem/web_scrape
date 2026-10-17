"""Evaluation endpoints: validate the body, then one call to ``src.services.evaluation_service``."""
from fastapi import APIRouter, BackgroundTasks

from src.api.errors import http_error
from src.core.errors import ServiceError
from src.models.evaluation import EvaluationRequest
from src.services import evaluation_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Core Evaluation
# ---------------------------------------------------------------------------

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
    try:
        return evaluation_service.start_core_evaluation(request.limit, request.output_json, background_tasks.add_task)
    except ServiceError as exc:
        raise http_error(exc)


# ---------------------------------------------------------------------------
# Graph Evaluation
# ---------------------------------------------------------------------------

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
    try:
        return evaluation_service.start_graph_evaluation(request.limit, request.output_json, background_tasks.add_task)
    except ServiceError as exc:
        raise http_error(exc)

