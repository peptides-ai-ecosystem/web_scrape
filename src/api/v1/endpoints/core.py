"""
Core data inspector endpoints.

Read-only endpoints that expose what currently lives in the **core** PostgreSQL
tables (peptides, benefits, side_effects, dosages, protocols, interactions,
indications, references, plus a graph-row summary). These endpoints power the
Core Data Inspector page at `/visualization/core.html`, but they are also
useful for ad-hoc DB inspection via Swagger or curl.

All queries go through the existing `DbPool` and entity repositories under
`src/infrastructure/db/`.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.v1.endpoints.graph import get_pool

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers (single-purpose SQL queries)
# ---------------------------------------------------------------------------


def _fetch_peptide_payload(db, peptide: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a base peptide row, fan out and fetch every related entity needed
    by the inspector. All queries use the same DbService connection so they
    share a transaction view.
    """
    peptide_id = peptide["id"]

    benefits = db.peptide.execute_all(
        """
        SELECT b.id, b.name, b.description, b.category, b.evidence_level,
               b.timeframe, pb.general_potency, pb.general_evidence_level,
               pb.sort_order
        FROM peptide_benefits pb
        JOIN benefits b ON b.id = pb.benefit_id
        WHERE pb.peptide_id = %s
        ORDER BY pb.sort_order NULLS LAST, b.name
        """,
        (peptide_id,),
    )

    side_effects = db.peptide.execute_all(
        """
        SELECT se.id, se.name, se.description, se.severity_level, se.frequency,
               se.category
        FROM peptide_side_effects pse
        JOIN side_effects se ON se.id = pse.side_effect_id
        WHERE pse.peptide_id = %s
        ORDER BY se.severity_level, se.name
        """,
        (peptide_id,),
    )

    interactions = db.peptide.execute_all(
        """
        SELECT pi.id, pi.peptide_id_1, pi.peptide_id_2,
               COALESCE(p2.name, pi.peptide_name_2) AS other_peptide_name,
               pi.interaction_type, pi.severity, pi.description, pi.recommendation
        FROM peptide_interactions pi
        LEFT JOIN peptides p2 ON p2.id = pi.peptide_id_2
        WHERE pi.peptide_id_1 = %s OR pi.peptide_id_2 = %s
        ORDER BY pi.interaction_type, other_peptide_name
        """,
        (peptide_id, peptide_id),
    )

    indications = db.peptide.execute_all(
        """
        SELECT id, indication_title, description, effectiveness_tag, created_at
        FROM peptide_research_indications
        WHERE peptide_id = %s
        ORDER BY effectiveness_tag, indication_title
        """,
        (peptide_id,),
    )

    for ind in indications:
        ind["studies"] = db.peptide.execute_all(
            """
            SELECT id, protocol_id, study_title, study_description
            FROM peptide_research_indication_studies
            WHERE indication_id = %s
            ORDER BY id
            """,
            (ind["id"],),
        )

    protocols = db.peptide.execute_all(
        """
        SELECT pp.id, pp.administration_method_id, am.name AS administration_method,
               pp.name, pp.description, pp.expectations, pp.quick_start_guide,
               pp.mechanism_of_action, pp.key_benefits, pp.best_timing,
               pp.effects_timeline, pp.is_recommended, pp.sort_order
        FROM peptide_protocols pp
        LEFT JOIN administration_methods am ON am.id = pp.administration_method_id
        WHERE pp.peptide_id = %s
        ORDER BY pp.sort_order NULLS LAST, am.name
        """,
        (peptide_id,),
    )

    for proto in protocols:
        protocol_id = proto["id"]

        proto["dosages"] = db.peptide.execute_all(
            """
            SELECT pd.id, pd.is_default, pd.is_required, pd.notes, pd.sort_order,
                   d.name AS dosage_name, d.amount AS dosage_amount, d.unit AS dosage_unit,
                   s.name AS schedule_name, s.frequency AS schedule_frequency,
                   s.timing AS schedule_timing, s.duration AS schedule_duration
            FROM protocol_dosages pd
            LEFT JOIN dosages d ON d.id = pd.dosage_id
            LEFT JOIN schedules s ON s.id = pd.schedule_id
            WHERE pd.protocol_id = %s
            ORDER BY pd.sort_order NULLS LAST, pd.id
            """,
            (protocol_id,),
        )

        proto["application_places"] = db.peptide.execute_all(
            """
            SELECT pap.id, pap.recommendation_level, pap.notes,
                   ap.name, ap.anatomical_region, ap.absorption_rate, ap.instructions
            FROM protocol_application_places pap
            JOIN application_places ap ON ap.id = pap.application_place_id
            WHERE pap.protocol_id = %s
            ORDER BY ap.name
            """,
            (protocol_id,),
        )

        proto["reconstitution_steps"] = db.peptide.execute_all(
            """
            SELECT step_number, description
            FROM peptide_protocol_reconstitution_steps
            WHERE protocol_id = %s
            ORDER BY step_number
            """,
            (protocol_id,),
        )

        proto["quality_indicators"] = db.peptide.execute_all(
            """
            SELECT indicator_title, indicator_description, sort_order
            FROM protocol_quality_indicators
            WHERE protocol_id = %s
            ORDER BY sort_order NULLS LAST, indicator_title
            """,
            (protocol_id,),
        )

    references = db.peptide.execute_all(
        """
        SELECT pr.id, pr.reference_type, pr.context,
               rs.id   AS study_id,    rs.title AS study_title,
               rs.authors AS study_authors, rs.journal AS study_journal,
               rs.publication_year AS study_year, rs.url AS study_url,
               c.id    AS citation_id, c.title AS citation_title,
               c.doi AS citation_doi, c.authors AS citation_authors,
               c.journal AS citation_journal, c.publication_year AS citation_year,
               c.publication_url AS citation_url
        FROM peptide_references pr
        LEFT JOIN research_studies rs ON rs.id = pr.study_id
        LEFT JOIN citations c        ON c.id = pr.citation_id
        WHERE pr.peptide_id = %s
        ORDER BY pr.reference_type, pr.id
        """,
        (peptide_id,),
    )

    graph_rows = db.peptide.execute_all(
        """
        SELECT pg.id, pg.administration_method_id, am.name AS administration_method,
               pg.time_range, pg.action_type,
               pg.peak_concentration, pg.half_life, pg.cleared_percentage,
               (pg.path_data IS NOT NULL AND pg.path_data <> '') AS has_path_data,
               COALESCE(jsonb_array_length(pg.points), 0)  AS point_count,
               COALESCE(jsonb_array_length(pg.markers), 0) AS marker_count
        FROM peptide_graph pg
        LEFT JOIN administration_methods am ON am.id = pg.administration_method_id
        WHERE pg.peptide_id = %s
        ORDER BY am.name, pg.time_range
        """,
        (peptide_id,),
    )

    return {
        "peptide": peptide,
        "benefits": benefits,
        "side_effects": side_effects,
        "interactions": interactions,
        "indications": indications,
        "protocols": protocols,
        "references": references,
        "graph": graph_rows,
    }


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
    q: Optional[str] = Query(
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
        with get_pool().acquire() as db:
            if q:
                like = f"%{q}%"
                rows = db.peptide.execute_all(
                    """
                    SELECT id, name, slug, category_id
                    FROM peptides
                    WHERE name ILIKE %s OR slug ILIKE %s
                    ORDER BY name
                    """,
                    (like, like),
                )
            else:
                rows = db.peptide.execute_all(
                    "SELECT id, name, slug, category_id FROM peptides ORDER BY name"
                )
            return [dict(r) for r in rows]
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
async def get_core_peptide_by_id(peptide_id: int):
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
        with get_pool().acquire() as db:
            peptide = db.peptide.get_by_id(peptide_id)
            if not peptide:
                raise HTTPException(status_code=404, detail=f"Peptide ID {peptide_id} not found")
            return _fetch_peptide_payload(db, dict(peptide))
    except HTTPException:
        raise
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
        with get_pool().acquire() as db:
            peptide = db.peptide.get_by_slug(slug)
            if not peptide:
                raise HTTPException(status_code=404, detail=f"Peptide slug '{slug}' not found")
            return _fetch_peptide_payload(db, dict(peptide))
    except HTTPException:
        raise
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
async def get_core_lookups() -> Dict[str, List[Dict[str, Any]]]:
    """
    Single round-trip that returns every lookup catalog. Cheap and stable —
    intended to be called once on page load so the inspector can map IDs back
    to names without further requests.
    """
    queries: Dict[str, str] = {
        "administration_methods": "SELECT id, name FROM administration_methods ORDER BY name",
        "benefits":               "SELECT id, name, category FROM benefits ORDER BY name",
        "side_effects":           "SELECT id, name, severity_level FROM side_effects ORDER BY name",
        "dosages":                "SELECT id, name, amount, unit FROM dosages ORDER BY name LIMIT 500",
        "schedules":              "SELECT id, name, frequency FROM schedules ORDER BY name",
        "application_places":     "SELECT id, name, anatomical_region FROM application_places ORDER BY name",
        "categories":             "SELECT id, category_name, slug FROM categories ORDER BY category_name",
    }

    result: Dict[str, List[Dict[str, Any]]] = {}
    try:
        with get_pool().acquire() as db:
            for key, sql in queries.items():
                try:
                    rows = db.peptide.execute_all(sql)
                    result[key] = [dict(r) for r in rows]
                except Exception as inner:
                    # A missing table shouldn't fail the whole call.
                    logger.warning(f"Lookup '{key}' failed: {inner}")
                    result[key] = []
        return result
    except Exception as e:
        logger.error(f"Failed to fetch lookups: {e}")
        raise HTTPException(status_code=500, detail=str(e))
