"""Interaction repository for peptide interaction operations."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository


class InteractionRepository(BaseRepository):
    """Repository for peptide interaction operations."""

    def upsert(self, peptide_id: int, interaction: Dict[str, Any]):
        """Upserts a peptide interaction."""
        with self.get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM peptide_interactions WHERE peptide_id_1 = %s AND LOWER(peptide_name_2) = LOWER(%s)",
                (peptide_id, interaction['secondary_peptide_name'])
            )
            row = cur.fetchone()
            if row:
                self.log_operation("EXIST_RELATION", "peptide_interactions", 
                    f"Peptide {peptide_id} <-> {interaction['secondary_peptide_name']}")
                return
            else:
                try:
                    itype = self._map_interaction_type(interaction.get('interaction_type', 'neutral'))
                    cur.execute(
                        "INSERT INTO peptide_interactions (peptide_id_1, peptide_name_2, interaction_type, description) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (peptide_id, interaction['secondary_peptide_name'], itype, interaction['description'])
                    )
                    self._commit()
                    if cur.rowcount > 0:
                        self.log_operation("INSERT_RELATION", "peptide_interactions", 
                            f"Peptide {peptide_id} <-> {interaction['secondary_peptide_name']} ({itype})")
                    else:
                        self.log_operation("EXIST_RELATION", "peptide_interactions (by index)", 
                            f"Peptide {peptide_id} <-> {interaction['secondary_peptide_name']}")
                except Exception as e:
                    self._rollback()
                    self.log_operation("ERROR_RELATION", "peptide_interactions", str(e))

    def _map_interaction_type(self, raw_type: str) -> str:
        """Maps raw interaction strings to DB enum values: synergistic, antagonistic, neutral, caution."""
        raw = str(raw_type).lower().strip()
        if any(x in raw for x in ["synergy", "increase", "boost", "positive", "complement"]):
            return "synergistic"
        if any(x in raw for x in ["antagon", "decrease", "block", "negative", "competit"]):
            return "antagonistic"
        if any(x in raw for x in ["caution", "danger", "warning", "risk", "monitor", "combinat", "compatib"]):
            return "caution"
        return "neutral"

    def get_by_peptide_id(self, peptide_id: int) -> list:
        """Get all interactions for a peptide."""
        return self.execute_all(
            "SELECT * FROM peptide_interactions WHERE peptide_id_1 = %s OR peptide_id_2 = %s",
            (peptide_id, peptide_id)
        )
