"""Read-only queries the evaluation package compares against the CSV.

One method per platform read model (the peptide, its relation names, its
protocols), so ``app/evaluation/`` holds only comparison logic and no SQL.
Rows come back as plain dicts; the connection's RealDictCursor makes them so.

Table names verified against live DB schema:
  peptide_protocols          (not 'protocols')
  peptide_graph              (not 'graph_data'; see GraphRepository)
  peptide_research_indications  (not 'peptide_indications')
  peptide_interactions       uses peptide_id_1, peptide_name_2
  protocol_dosages           links via dosage_id FK -> dosages table
"""

from typing import Any

from app.repositories.base import BaseRepository


class EvaluationRepository(BaseRepository):
    """Repository for the evaluation reads (actual state of a synced peptide)."""

    def _q(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Run a query and return rows as list of dicts.

        Works with both regular cursors (rows are tuples) and
        RealDictCursor (rows are dict-like) - the project uses RealDictCursor.
        """
        with self.get_cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            rows = cur.fetchall()
            if not rows:
                return []
            if hasattr(rows[0], "keys"):
                return [dict(r) for r in rows]
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row, strict=False)) for row in rows]

    def get_peptide_by_slug(self, slug: str) -> dict[str, Any] | None:
        rows = self._q(
            "SELECT id, name, slug, synonyms, overview, mechanism_of_action, "
            "       sequence, cycle_duration, storage_temperature, "
            "       fda_approval_status, wada_status, stop_signs, key_information "
            "FROM peptides WHERE slug = %s LIMIT 1",
            (slug,),
        )
        return rows[0] if rows else None

    def benefit_names(self, peptide_id: int) -> list[str]:
        rows = self._q(
            "SELECT b.name FROM benefits b JOIN peptide_benefits pb ON pb.benefit_id = b.id WHERE pb.peptide_id = %s",
            (peptide_id,),
        )
        return [r["name"] for r in rows]

    def side_effect_names(self, peptide_id: int) -> list[str]:
        rows = self._q(
            "SELECT se.name FROM side_effects se "
            "JOIN peptide_side_effects pse ON pse.side_effect_id = se.id "
            "WHERE pse.peptide_id = %s",
            (peptide_id,),
        )
        return [r["name"] for r in rows]

    def dosages(self, peptide_id: int) -> list[dict[str, Any]]:
        """Fetch dosages linked via peptide_protocols -> protocol_dosages -> dosages."""
        rows = self._q(
            "SELECT DISTINCT d.amount, d.unit "
            "FROM dosages d "
            "JOIN protocol_dosages pd ON pd.dosage_id = d.id "
            "JOIN peptide_protocols pp ON pp.id = pd.protocol_id "
            "WHERE pp.peptide_id = %s",
            (peptide_id,),
        )
        return rows

    def schedule_names(self, peptide_id: int) -> list[str]:
        """Fetch schedules linked via peptide_protocols -> protocol_dosages -> schedules."""
        rows = self._q(
            "SELECT DISTINCT s.name FROM schedules s "
            "JOIN protocol_dosages pd ON pd.schedule_id = s.id "
            "JOIN peptide_protocols pp ON pp.id = pd.protocol_id "
            "WHERE pp.peptide_id = %s",
            (peptide_id,),
        )
        return [r["name"] for r in rows]

    def administration_method_names(self, peptide_id: int) -> list[str]:
        rows = self._q(
            "SELECT DISTINCT am.name "
            "FROM administration_methods am "
            "JOIN peptide_protocols pp ON pp.administration_method_id = am.id "
            "WHERE pp.peptide_id = %s",
            (peptide_id,),
        )
        return [r["name"] for r in rows]

    def interactions(self, peptide_id: int) -> list[dict[str, Any]]:
        # Interactions use peptide_id_1 (primary) and peptide_name_2 (secondary name)
        rows = self._q(
            "SELECT peptide_name_2 AS secondary_peptide_name, "
            "       interaction_type, description "
            "FROM peptide_interactions WHERE peptide_id_1 = %s",
            (peptide_id,),
        )
        return rows

    def indications(self, peptide_id: int) -> list[dict[str, Any]]:
        rows = self._q(
            "SELECT indication_title, effectiveness_tag, description "
            "FROM peptide_research_indications WHERE peptide_id = %s",
            (peptide_id,),
        )
        return rows

    def protocols(self, peptide_id: int) -> list[dict[str, Any]]:
        rows = self._q(
            "SELECT id, name, description, administration_method_id, "
            "       best_timing, effects_timeline "
            "FROM peptide_protocols WHERE peptide_id = %s AND deleted_at IS NULL",
            (peptide_id,),
        )
        return rows

    def count_references(self, peptide_id: int) -> int:
        rows = self._q("SELECT COUNT(*) AS cnt FROM peptide_references WHERE peptide_id = %s", (peptide_id,))
        return rows[0]["cnt"] if rows else 0
