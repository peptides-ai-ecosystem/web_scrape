"""
DbActualFetcher
===============
Queries the live database for the *actual* state of a peptide after sync
and returns it in the same shape as CsvExpectationBuilder produces, so
EvaluationEngine can do a direct comparison.

Table names verified against live DB schema:
  peptide_protocols          (not 'protocols')
  peptide_graph              (not 'graph_data')
  peptide_research_indications  (not 'peptide_indications')
  peptide_interactions       uses peptide_id_1, peptide_name_2
  protocol_dosages           links via dosage_id FK -> dosages table
"""
from typing import Any, Dict, List, Optional
from src.infrastructure.db.service import DbManager


class DbActualFetcher:
    """Fetches actual DB state for a peptide using existing repository methods."""

    def __init__(self, db_url: str):
        self._db = DbManager(db_url)
        self._db.connect()

    def close(self):
        self._db.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Return the actual DB state for a peptide (by slug), or None if
        the peptide does not exist yet.

        Shape mirrors CsvExpectationBuilder.build() output:
            {
              "peptide"              : dict,
              "benefits"             : list[str],   # names
              "side_effects"         : list[str],
              "dosages"              : list[dict],  # {amount, unit}
              "schedules"            : list[str],
              "administration_methods": list[str],
              "interactions"         : list[dict],
              "indications"          : list[dict],
              "protocols"            : list[dict],
              "references_count"     : int,
              "graph_data_count"     : int,
            }
        """
        conn = self._db.conn
        if conn is None or conn.closed:
            self._db.connect()
            conn = self._db.conn

        peptide = self._fetch_peptide(conn, slug)
        if not peptide:
            return None

        pid = peptide["id"]

        return {
            "peptide": peptide,
            "benefits": self._fetch_benefit_names(conn, pid),
            "side_effects": self._fetch_side_effect_names(conn, pid),
            "dosages": self._fetch_dosages(conn, pid),
            "schedules": self._fetch_schedule_names(conn, pid),
            "administration_methods": self._fetch_admin_methods(conn, pid),
            "interactions": self._fetch_interactions(conn, pid),
            "indications": self._fetch_indications(conn, pid),
            "protocols": self._fetch_protocols(conn, pid),
            "references_count": self._count_references(conn, pid),
            # NOTE: graph_data_count removed — graph evaluation is handled
            # by GraphEvaluator via /evaluation/graph
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _q(self, conn, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Run a query and return rows as list of dicts.

        Works with both regular cursors (rows are tuples) and
        RealDictCursor (rows are dict-like) — the project uses RealDictCursor.
        """
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            rows = cur.fetchall()
            if not rows:
                return []
            # RealDictCursor rows are dict-like — convert directly.
            # Regular cursor rows are tuples — zip with column names.
            if hasattr(rows[0], 'keys'):
                return [dict(r) for r in rows]
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]

    def _fetch_peptide(self, conn, slug: str) -> Optional[Dict[str, Any]]:
        rows = self._q(conn,
            "SELECT id, name, slug, synonyms, overview, mechanism_of_action, "
            "       sequence, cycle_duration, storage_temperature, "
            "       fda_approval_status, wada_status, stop_signs, key_information "
            "FROM peptides WHERE slug = %s LIMIT 1",
            (slug,)
        )
        return rows[0] if rows else None

    def _fetch_benefit_names(self, conn, peptide_id: int) -> List[str]:
        rows = self._q(conn,
            "SELECT b.name FROM benefits b "
            "JOIN peptide_benefits pb ON pb.benefit_id = b.id "
            "WHERE pb.peptide_id = %s",
            (peptide_id,)
        )
        return [r["name"] for r in rows]

    def _fetch_side_effect_names(self, conn, peptide_id: int) -> List[str]:
        rows = self._q(conn,
            "SELECT se.name FROM side_effects se "
            "JOIN peptide_side_effects pse ON pse.side_effect_id = se.id "
            "WHERE pse.peptide_id = %s",
            (peptide_id,)
        )
        return [r["name"] for r in rows]

    def _fetch_dosages(self, conn, peptide_id: int) -> List[Dict[str, Any]]:
        """Fetch dosages linked via peptide_protocols -> protocol_dosages -> dosages."""
        rows = self._q(conn,
            "SELECT DISTINCT d.amount, d.unit "
            "FROM dosages d "
            "JOIN protocol_dosages pd ON pd.dosage_id = d.id "
            "JOIN peptide_protocols pp ON pp.id = pd.protocol_id "
            "WHERE pp.peptide_id = %s",
            (peptide_id,)
        )
        return rows

    def _fetch_schedule_names(self, conn, peptide_id: int) -> List[str]:
        """Fetch schedules linked via peptide_protocols -> protocol_dosages -> schedules."""
        rows = self._q(conn,
            "SELECT DISTINCT s.name FROM schedules s "
            "JOIN protocol_dosages pd ON pd.schedule_id = s.id "
            "JOIN peptide_protocols pp ON pp.id = pd.protocol_id "
            "WHERE pp.peptide_id = %s",
            (peptide_id,)
        )
        return [r["name"] for r in rows]

    def _fetch_admin_methods(self, conn, peptide_id: int) -> List[str]:
        rows = self._q(conn,
            "SELECT DISTINCT am.name "
            "FROM administration_methods am "
            "JOIN peptide_protocols pp ON pp.administration_method_id = am.id "
            "WHERE pp.peptide_id = %s",
            (peptide_id,)
        )
        return [r["name"] for r in rows]

    def _fetch_interactions(self, conn, peptide_id: int) -> List[Dict[str, Any]]:
        # Interactions use peptide_id_1 (primary) and peptide_name_2 (secondary name)
        rows = self._q(conn,
            "SELECT peptide_name_2 AS secondary_peptide_name, "
            "       interaction_type, description "
            "FROM peptide_interactions WHERE peptide_id_1 = %s",
            (peptide_id,)
        )
        return rows

    def _fetch_indications(self, conn, peptide_id: int) -> List[Dict[str, Any]]:
        rows = self._q(conn,
            "SELECT indication_title, effectiveness_tag, description "
            "FROM peptide_research_indications WHERE peptide_id = %s",
            (peptide_id,)
        )
        return rows

    def _fetch_protocols(self, conn, peptide_id: int) -> List[Dict[str, Any]]:
        rows = self._q(conn,
            "SELECT id, name, description, administration_method_id, "
            "       best_timing, effects_timeline "
            "FROM peptide_protocols WHERE peptide_id = %s AND deleted_at IS NULL",
            (peptide_id,)
        )
        return rows

    def _count_references(self, conn, peptide_id: int) -> int:
        rows = self._q(conn,
            "SELECT COUNT(*) AS cnt FROM peptide_references "
            "WHERE peptide_id = %s",
            (peptide_id,)
        )
        return rows[0]["cnt"] if rows else 0
