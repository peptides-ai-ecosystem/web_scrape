import os
from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv
import sys
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Add project root to path if needed for local imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.infrastructure.db import DbPool

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level connection pool (minconn=1, maxconn=5).
# Connections are checked out per request and returned automatically via the
# DbPool.acquire() context manager — no new TCP sockets per request, and each
# concurrent user gets their own connection so cursors never collide.
# ---------------------------------------------------------------------------
_pool: DbPool | None = None


def get_pool() -> DbPool:
    global _pool
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    if _pool is None:
        _pool = DbPool(db_url, minconn=1, maxconn=5)
    return _pool


# ---------------------------------------------------------------------------
# Response schemas (documentation only — also used as return types)
# ---------------------------------------------------------------------------

class PeptideItem(BaseModel):
    id: int = Field(..., description="Peptide database ID.")
    name: str = Field(..., description="Peptide display name.")


class MethodItem(BaseModel):
    id: int = Field(..., description="Administration method database ID.")
    name: str = Field(..., description="Administration method name (e.g. 'Injectable', 'Oral').")


# NOTE: Intentionally not declared as a strict Pydantic response_model.
# The repository (`GraphRepository.get_visualization_data`) returns a
# time-range nested dict — `{peptide_name, administration_method, "24h": {...},
# "7d": {...}, "14d": {...}, "30d": {...}}` — and the frontend in
# `script.js` indexes into `graphData[currentRange]` directly. Pydantic
# rejects this dynamic schema, so we document it via the `responses` block
# and return the raw dict.


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/peptides",
    response_model=List[PeptideItem],
    responses={
        200: {
            "description": "List of peptides that have at least one graph data row in `peptide_graph`.",
            "content": {
                "application/json": {
                    "example": [
                        {"id": 1, "name": "Semaglutide"},
                        {"id": 2, "name": "Tirzepatide"},
                        {"id": 3, "name": "Insulin Glargine"},
                    ]
                }
            },
        },
        500: {"description": "Database connection error or query failure."},
    },
)
async def get_peptides():
    """
    📋 List all peptides that have **graph data available**.

    Queries the `peptide_graph` table and returns only peptides that have
    at least one row (i.e., at least one administration method with data).

    ### Response
    Array of `{{"id": <int>, "name": <string>}}` sorted alphabetically by name.

    ### Errors
    - **500** → Database query failed or `DATABASE_URL` is not set.
    """
    try:
        with get_pool().acquire() as db:
            peptides = db.graph.execute_all("""
                SELECT DISTINCT p.id, p.name
                FROM peptides p
                JOIN peptide_graph pg ON p.id = pg.peptide_id
                ORDER BY p.name
            """)
            return [{"id": row["id"], "name": row["name"]} for row in peptides]
    except Exception as e:
        logger.error(f"Failed to fetch peptides: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch peptides: {str(e)}")


@router.get(
    "/peptide/{peptide_id}/methods",
    response_model=List[MethodItem],
    responses={
        200: {
            "description": "List of administration methods with graph data for the given peptide.",
            "content": {
                "application/json": {
                    "example": [
                        {"id": 1, "name": "Injectable"},
                        {"id": 2, "name": "Oral"},
                        {"id": 3, "name": "Sublingual"},
                    ]
                }
            },
        },
        404: {"description": "No methods found — peptide may not exist or has no graph data."},
        500: {"description": "Database error."},
    },
)
async def get_peptide_methods(peptide_id: int):
    """
    🔬 Get all **administration methods** available for a peptide's graph data.

    Use the `peptide_id` from `/peptides` to discover which methods can be
    passed to `GET /graph/{peptide_id}?method=...`.

    ### Path Parameters
    - `peptide_id` — numeric ID of the peptide (from `/peptides`).

    ### Response
    Array of `{{"id": <int>, "name": "<string>"}}`.

    ### Errors
    - **404** → Peptide not found or has no graph data.
    - **500** → Database error.
    """
    try:
        with get_pool().acquire() as db:
            methods = db.graph.get_methods_for_peptide(peptide_id)
        if not methods:
            raise HTTPException(
                status_code=404,
                detail=f"No graph data found for peptide ID {peptide_id}",
            )
        return methods
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch methods for peptide {peptide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/graph/{peptide_id}",
    responses={
        200: {
            "description": "Pharmacokinetics graph data keyed by time range.",
            "content": {
                "application/json": {
                    "example": {
                        "peptide_name": "BPC-157",
                        "administration_method": "Injectable",
                        "24h": {
                            "metadata": {"peak": "48 min", "half_life": "8 hrs", "cleared": "~1.7 days"},
                            "path_data": "M 10 35 C 10.258 35, ...",
                            "markers": [{"r": 0.7, "cx": 41.82, "cy": 20.60, "fill": "#f59e0b"}],
                            "points":  [{"x": 10.0, "y": 35.0}, {"x": 10.86, "y": 26.3}],
                            "x_labels": [{"pos": 10.0, "label": "Dose"}, {"pos": 96.0, "label": "1d"}],
                            "y_labels": [{"pos": 8.0,  "label": "100%"}, {"pos": 21.3, "label": "50%"}],
                            "legend":   {"peak": "rgb(34, 197, 94)", "half-life": "rgb(245, 158, 11)"},
                        },
                        "7d":  {"metadata": {}, "path_data": "...", "markers": [], "points": [], "x_labels": [], "y_labels": [], "legend": {}},
                        "14d": {"metadata": {}, "path_data": "...", "markers": [], "points": [], "x_labels": [], "y_labels": [], "legend": {}},
                        "30d": {"metadata": {}, "path_data": "...", "markers": [], "points": [], "x_labels": [], "y_labels": [], "legend": {}},
                    }
                }
            },
        },
        404: {"description": "No graph data for this peptide + method combination."},
        422: {
            "description": "Validation error — invalid `method` value. "
                            "Must be one of the methods returned by `/peptide/{id}/methods`."
        },
        500: {"description": "Database error."},
    },
)
async def get_graph_data(
    peptide_id: int,
    method: str = Query(
        "Injectable",
        description="Administration method for the graph. Use `/peptide/{id}/methods` to discover valid options.",
        examples=["Injectable", "Oral", "Sublingual"],
    ),
):
    """
    📈 Fetch **pharmacokinetics graph data** for a peptide and administration method.

    The response is keyed by time range (`24h`, `7d`, `14d`, `30d`) — each one
    contains `path_data` (SVG curve), `points`, `markers`, axis labels, legend
    color map, and a `metadata` block with peak / half-life / cleared values.
    The frontend in `script.js` switches the rendered curve by indexing into
    `graphData[currentRange]`.

    ### Path Parameters
    - `peptide_id` — numeric ID from `/peptides`.

    ### Query Parameters
    - `method` — administration method (default: `"Injectable"`).

    ### Errors
    - **404** → No graph data for this peptide + method combination.
    - **500** → Database error.
    """
    try:
        with get_pool().acquire() as db:
            data = db.graph.get_visualization_data(peptide_id, method)
        if not data or not any(
            k not in ["peptide_name", "administration_method"] for k in data.keys()
        ):
            raise HTTPException(
                status_code=404,
                detail=f"No graph data found for peptide {peptide_id} with method '{method}'",
            )
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch graph data for peptide {peptide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

