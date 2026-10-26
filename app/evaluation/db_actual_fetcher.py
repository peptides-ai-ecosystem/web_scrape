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

from typing import Any

from app.infrastructure.db.service import DbManager
from app.repositories.evaluation_repository import EvaluationRepository


class DbActualFetcher:
    """Assembles the actual DB state for a peptide from EvaluationRepository reads."""

    def __init__(self, db_url: str, repository: EvaluationRepository | None = None):
        self._db = DbManager(db_url)
        self._db.connect()
        self._repo = repository or EvaluationRepository(self._db)

    def close(self):
        self._db.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, slug: str) -> dict[str, Any] | None:
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
        repo = self._repo
        peptide = repo.get_peptide_by_slug(slug)
        if not peptide:
            return None

        pid = peptide["id"]

        return {
            "peptide": peptide,
            "benefits": repo.benefit_names(pid),
            "side_effects": repo.side_effect_names(pid),
            "dosages": repo.dosages(pid),
            "schedules": repo.schedule_names(pid),
            "administration_methods": repo.administration_method_names(pid),
            "interactions": repo.interactions(pid),
            "indications": repo.indications(pid),
            "protocols": repo.protocols(pid),
            "references_count": repo.count_references(pid),
            # NOTE: graph_data_count removed — graph evaluation is handled
            # by GraphEvaluator via /evaluation/graph
        }
