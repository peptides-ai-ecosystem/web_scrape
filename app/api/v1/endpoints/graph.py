"""PK graph endpoints: status codes plus one call to ``app.services.graph_service``."""
import logging
from typing import List

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.errors import http_error
from app.core.errors import ServiceError
from app.models.graph import MethodItem, PeptideItem
from app.services import graph_service

router = APIRouter()
logger = logging.getLogger(__name__)


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
        return graph_service.list_peptides_with_graph()
    except Exception as e:
        logger.error(f"Failed to fetch peptides: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch peptides: {str(e)}")


@router.get(
    "/pk/peptides",
    responses={
        200: {
            "description": "Every peptide with PK curves, with source, last write time and a headline summary.",
            "content": {
                "application/json": {
                    "example": {
                        "count": 1,
                        "peptides": [
                            {
                                "id": 12,
                                "name": "BPC-157",
                                "slug": "bpc-157",
                                "source": "pep-pedia.org",
                                "source_url": "https://pep-pedia.org/peptides/bpc-157",
                                "methods": ["Injectable", "Oral"],
                                "curve_count": 8,
                                "last_updated": "2026-10-01T03:15:00",
                                "action_type": "scraped",
                                "headline": {
                                    "method": "Injectable",
                                    "half_life": "8 hrs",
                                    "peak": "48 min",
                                    "cleared": "~1.7 days",
                                },
                            }
                        ],
                    }
                }
            },
        },
        500: {"description": "Database error."},
    },
)
async def get_pk_summary():
    """
    📋 List peptides with **pharmacokinetics curves**, for the admin PK tab.

    Like `GET /peptides` but with what an admin needs to judge the data: the
    administration methods available, how many curve rows exist, when the
    newest row was written (`last_updated`, the last scrape or manual edit),
    whether it was `scraped` or `manual`, the pep-pedia.org source page
    (derived from the peptide slug) and a headline half-life / peak / cleared
    summary (Injectable 24h preferred).

    ### Errors
    - **500** → Database query failed or `DATABASE_URL` is not set.
    """
    try:
        return graph_service.list_pk_summary()
    except Exception as e:
        logger.error(f"Failed to fetch PK summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch PK summary.")


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
async def get_peptide_methods(
    peptide_id: int = Path(
        ...,
        ge=1,
        description="Numeric peptide database ID (from `GET /api/v1/peptides`).",
    ),
):
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
    - **422** → `peptide_id` is not a positive integer.
    - **500** → Database error.
    """
    try:
        return graph_service.methods_for_peptide(peptide_id)
    except ServiceError as exc:
        raise http_error(exc)
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
    peptide_id: int = Path(
        ...,
        ge=1,
        description="Numeric peptide database ID (from `GET /api/v1/peptides`).",
    ),
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
    - **404** → Peptide not found or has no graph data.
    - **422** → Invalid `method` value, or `peptide_id` is not a positive integer.
    - **500** → Database error.
    """
    try:
        return graph_service.graph_data(peptide_id, method)
    except ServiceError as exc:
        raise http_error(exc)
    except Exception as e:
        logger.error(f"Failed to fetch graph data for peptide {peptide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

