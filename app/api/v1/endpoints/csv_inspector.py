"""
CSV inspector endpoints.

Read-only endpoints that surface what was **scraped** into the enhanced CSV at
`output/pep_pedia_enhanced.csv` (path comes from `app.core.config.ENHANCED_CSV`).
The Core Data Inspector page renders these alongside the `/core/*` endpoints
so the operator can spot ingestion gaps between scrape and DB injection.

The reading, caching and grouping live in `app/services/csv_inspector_service.py`.
"""

from fastapi import APIRouter, Query

from app.api.errors import http_error
from app.core.errors import ServiceError
from app.services import csv_inspector_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/peptides",
    responses={
        200: {
            "description": "Distinct (peptide, method) tuples found in the CSV.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "name": "BPC-157",
                            "method": "Injectable",
                            "url": "https://pep-pedia.org/peptide/bpc-157",
                            "slug": "bpc-157",
                        },
                    ]
                }
            },
        },
        404: {"description": "Master CSV file not found (no scrape has been run yet)."},
    },
)
async def list_csv_peptides(
    q: str | None = Query(
        None,
        description="Case-insensitive substring filter applied to `Peptide_Name`.",
    ),
):
    """
    List every peptide row in the master CSV.

    Each entry is a `(name, method, url, slug)` tuple — the slug is derived
    from the name, so it can be used to look the same peptide up in the
    database via `/api/v1/core/peptide/by-slug/{slug}`.
    """
    try:
        return csv_inspector_service.list_peptides(q)
    except ServiceError as exc:
        raise http_error(exc)


@router.get(
    "/peptide",
    responses={
        200: {
            "description": "Grouped non-empty cells for one peptide row.",
        },
        404: {"description": "No CSV row matches the given peptide name (and method, if provided)."},
    },
)
async def get_csv_peptide(
    name: str = Query(
        ...,
        description="Peptide name (case-insensitive). Slug also accepted.",
        examples=["BPC-157", "bpc-157", "MK-677"],
    ),
    method: str | None = Query(
        None,
        description="Optional administration method to disambiguate when a peptide has multiple rows.",
        examples=["Injectable", "Oral"],
    ),
):
    """
    Return the CSV row for one peptide, with cells **grouped by entity** and
    empty cells dropped. The `graph` group is JSON-decoded for convenience.

    Resolution order:

    1. `(name.lower(), method.lower())` exact match
    2. `name.lower()` exact match
    3. `slug(name)` match (e.g. `BPC-157` → `bpc-157`)
    """
    try:
        return csv_inspector_service.get_peptide(name, method)
    except ServiceError as exc:
        raise http_error(exc)


@router.get(
    "/columns",
    responses={
        200: {
            "description": "All CSV column names grouped by their conceptual entity prefix.",
            "content": {
                "application/json": {
                    "example": {
                        "total": 2443,
                        "groups": {
                            "identity": ["Peptide_Name", "Full_Name", "Method", "URL"],
                            "overview": ["overview_what_is_bpc-157", "overview_key_benefits"],
                        },
                    }
                }
            },
        },
        404: {"description": "Master CSV file not found."},
    },
)
async def list_csv_columns():
    """
    Return every CSV header bucketed by entity group. Useful while building
    or debugging mappers — you can immediately see which raw scrape columns
    map to which database entity group.
    """
    try:
        return csv_inspector_service.list_columns()
    except ServiceError as exc:
        raise http_error(exc)
