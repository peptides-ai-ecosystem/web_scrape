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
    administration_method: str = Field(..., description="Administration method name (e.g. 'Injectable', 'Oral').")


class GraphDataResponse(BaseModel):
    peptide_name: str = Field(..., description="Peptide display name.")
    administration_method: str = Field(..., description="Administration method for this graph.")
    time_ranges: List[str] = Field(..., description="X-axis time range labels (e.g. ['0h', '1h', '2h', '4h', '8h', '12h', '24h']).")
    concentration_values: List[float] = Field(..., description="Y-axis concentration values matching each time range.")
    svg_path: str = Field(..., description="SVG path string (M/L/C commands) for the concentration curve.")
    points: List[Dict[str, float]] = Field(..., description="Coordinate points on the curve as [{{'x': ..., 'y': ...}}].")
    markers: List[Dict[str, Any]] = Field(..., description="Marker annotations for notable data points.")
    x_label: str = Field("Time", description="X-axis label.")
    y_label: str = Field("Concentration", description="Y-axis label.")


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
                        {"administration_method": "Injectable"},
                        {"administration_method": "Oral"},
                        {"administration_method": "Sublingual"},
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
    Array of `{{"administration_method": "<string>"}}`.

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
    response_model=GraphDataResponse,
    responses={
        200: {
            "description": "Full pharmacokinetics graph data for rendering a concentration—time curve.",
            "content": {
                "application/json": {
                    "example": {
                        "peptide_name": "Semaglutide",
                        "administration_method": "Injectable",
                        "time_ranges": ["0h", "1h", "2h", "4h", "8h", "12h", "24h"],
                        "concentration_values": [0.0, 1.2, 2.8, 4.1, 3.5, 1.8, 0.3],
                        "svg_path": "M0,100 L50,80 L100,40 L200,20 L300,10 L400,30 L500,70",
                        "points": [
                            {"x": 0, "y": 100},
                            {"x": 50, "y": 80},
                            {"x": 100, "y": 40},
                        ],
                        "markers": [
                            {"label": "Tmax", "x": 200, "y": 20},
                            {"label": "Cmax", "x": 200, "y": 20},
                        ],
                        "x_label": "Time (hours)",
                        "y_label": "Concentration (ng/mL)",
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

    Returns everything needed to render an interactive concentration—time curve:
    SVG path, coordinate points, time-range/concentration arrays, and markers.

    ### Path Parameters
    - `peptide_id` — numeric ID from `/peptides`.

    ### Query Parameters
    - `method` — administration method (default: `"Injectable"`).

    ### Response
    JSON with `svg_path`, `points`, `markers`, `time_ranges`, `concentration_values`,
    and axis labels. See the schema for full details.

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

