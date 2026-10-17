"""Read-only queries behind the Core Data Inspector (``/api/v1/core/*``).

Every query reads platform-owned tables (XR-8); nothing here writes. The
inspector page at ``/visualization/core.html`` renders the results.
"""

import logging
from typing import Any

from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

# Every lookup catalog the inspector maps IDs back to names with.
LOOKUP_QUERIES: dict[str, str] = {
    "administration_methods": "SELECT id, name FROM administration_methods ORDER BY name",
    "benefits": "SELECT id, name, category FROM benefits ORDER BY name",
    "side_effects": "SELECT id, name, severity_level FROM side_effects ORDER BY name",
    "dosages": "SELECT id, name, amount, unit FROM dosages ORDER BY name LIMIT 500",
    "schedules": "SELECT id, name, frequency FROM schedules ORDER BY name",
    "application_places": "SELECT id, name, anatomical_region FROM application_places ORDER BY name",
    "categories": "SELECT id, category_name, slug FROM categories ORDER BY category_name",
}


class PeptideInspectorRepository(BaseRepository):
    """Fan-out reads for one peptide, the peptide list and the lookup catalogs."""

    def list_peptides(self, q: str | None = None) -> list[dict[str, Any]]:
        """Every peptide (id, name, slug, category_id), optionally filtered by name/slug substring."""
        if q:
            like = f"%{q}%"
            rows = self.execute_all(
                """
                SELECT id, name, slug, category_id
                FROM peptides
                WHERE name ILIKE %s OR slug ILIKE %s
                ORDER BY name
                """,
                (like, like),
            )
        else:
            rows = self.execute_all("SELECT id, name, slug, category_id FROM peptides ORDER BY name")
        return [dict(r) for r in rows]

    def fetch_payload(self, peptide: dict[str, Any]) -> dict[str, Any]:
        """
        Given a base peptide row, fan out and fetch every related entity needed
        by the inspector. All queries use the same connection so they share a
        transaction view.
        """
        peptide_id = peptide["id"]

        benefits = self.execute_all(
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

        side_effects = self.execute_all(
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

        interactions = self.execute_all(
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

        indications = self.execute_all(
            """
            SELECT id, indication_title, description, effectiveness_tag, created_at
            FROM peptide_research_indications
            WHERE peptide_id = %s
            ORDER BY effectiveness_tag, indication_title
            """,
            (peptide_id,),
        )

        for ind in indications:
            ind["studies"] = self.execute_all(
                """
                SELECT id, protocol_id, study_title, study_description
                FROM peptide_research_indication_studies
                WHERE indication_id = %s
                ORDER BY id
                """,
                (ind["id"],),
            )

        protocols = self.execute_all(
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

            proto["dosages"] = self.execute_all(
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

            proto["application_places"] = self.execute_all(
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

            proto["reconstitution_steps"] = self.execute_all(
                """
                SELECT step_number, description
                FROM peptide_protocol_reconstitution_steps
                WHERE protocol_id = %s
                ORDER BY step_number
                """,
                (protocol_id,),
            )

            proto["quality_indicators"] = self.execute_all(
                """
                SELECT indicator_title, indicator_description, sort_order
                FROM protocol_quality_indicators
                WHERE protocol_id = %s
                ORDER BY sort_order NULLS LAST, indicator_title
                """,
                (protocol_id,),
            )

        references = self.execute_all(
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

        graph_rows = self.execute_all(
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

    def lookups(self) -> dict[str, list[dict[str, Any]]]:
        """Every lookup catalog in one round-trip; a missing table yields an empty list."""
        result: dict[str, list[dict[str, Any]]] = {}
        for key, sql in LOOKUP_QUERIES.items():
            try:
                rows = self.execute_all(sql)
                result[key] = [dict(r) for r in rows]
            except Exception as inner:
                # A missing table shouldn't fail the whole call.
                logger.warning(f"Lookup '{key}' failed: {inner}")
                result[key] = []
        return result
