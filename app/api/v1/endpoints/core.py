"""
Core data inspector endpoints.

Read-only endpoints that expose what currently lives in the **core** PostgreSQL
tables (peptides, benefits, side_effects, dosages, protocols, interactions,
indications, references, plus a graph-row summary). These endpoints power the
Core Data Inspector page at `/visualization/core.html`, but they are also
useful for ad-hoc DB inspection via Swagger or curl.

All queries live in `app/repositories/peptide_inspector.py`;
these routes call `app/services/core_data_service.py`.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.errors import http_error
from app.core.errors import ServiceError
from app.services import core_data_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/peptides",
    responses={
        200: {
            "description": "List of every peptide currently present in the `peptides` table.",
            "content": {
                "application/json": {
                    "example": [
                        {"id": 1, "name": "BPC-157", "slug": "bpc-157", "category_id": 2},
                        {"id": 2, "name": "MK-677", "slug": "mk-677", "category_id": 4},
                    ]
                }
            },
        },
        500: {"description": "Database error."},
    },
)
async def list_core_peptides(
    q: str | None = Query(
        None,
        description="Optional case-insensitive substring filter on peptide name or slug.",
        examples=["bpc", "mk-677"],
    ),
):
    """
    List all peptides currently injected in the **core** database.

    Used by the Core Data Inspector dropdown.
    """
    try:
        return core_data_service.list_peptides(q)
    except Exception as e:
        logger.error(f"Failed to list core peptides: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/peptide/{peptide_id}",
    responses={
        200: {"description": "Fully normalized peptide record with all related entities."},
        404: {"description": "Peptide ID not found."},
        500: {"description": "Database error."},
    },
)
async def get_core_peptide_by_id(
    peptide_id: int = Path(
        ...,
        ge=1,
        description="Numeric peptide database ID.",
    ),
):
    """
    Return everything we have in the database for a single peptide:
    benefits, side effects, interactions, indications (+ studies),
    protocols (+ dosages, application places, reconstitution steps, quality
    indicators), references (research studies + citations), and a summary
    of `peptide_graph` rows.

    Mirrors the structure of the external monorepo's schema modules
    `shared/peptides`, `shared/protocols`, and `shared/protocols/research`.
    """
    try:
        return core_data_service.peptide_by_id(peptide_id)
    except ServiceError as exc:
        raise http_error(exc)
    except Exception as e:
        logger.error(f"Failed to fetch core peptide {peptide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/peptide/by-slug/{slug}",
    responses={
        200: {"description": "Fully normalized peptide record looked up by slug."},
        404: {"description": "Peptide with that slug not found."},
        500: {"description": "Database error."},
    },
)
async def get_core_peptide_by_slug(slug: str):
    """
    Same payload as `/core/peptide/{id}` but keyed by slug — useful for joining
    against CSV rows where only the peptide name/slug is known.
    """
    try:
        return core_data_service.peptide_by_slug(slug)
    except ServiceError as exc:
        raise http_error(exc)
    except Exception as e:
        logger.error(f"Failed to fetch core peptide slug={slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/lookups",
    responses={
        200: {
            "description": "All lookup catalogs in one round-trip — used to render legend keys and badges.",
            "content": {
                "application/json": {
                    "example": {
                        "administration_methods": [{"id": 1, "name": "Oral"}],
                        "benefits": [{"id": 1, "name": "Muscle Growth"}],
                        "side_effects": [{"id": 1, "name": "Headache"}],
                        "dosages": [{"id": 1, "name": "1mg"}],
                        "schedules": [{"id": 1, "name": "Daily"}],
                        "application_places": [{"id": 1, "name": "Abdomen"}],
                        "categories": [{"id": 1, "category_name": "GHS"}],
                    }
                }
            },
        },
        500: {"description": "Database error."},
    },
)
async def get_core_lookups() -> dict[str, list[dict[str, Any]]]:
    """
    Single round-trip that returns every lookup catalog. Cheap and stable —
    intended to be called once on page load so the inspector can map IDs back
    to names without further requests.
    """
    try:
        return core_data_service.lookups()
    except Exception as e:
        logger.error(f"Failed to fetch lookups: {e}")
        raise HTTPException(status_code=500, detail=str(e))
