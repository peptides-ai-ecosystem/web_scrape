"""Interaction repository for peptide interaction operations."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository


# Exact mapping from raw CSV interaction keywords to PostgreSQL
# interaction_type enum values (synergistic, antagonistic, neutral, caution).
_INTERACTION_TYPE_MAP = {
    "synergistic": "synergistic",
    "antagonistic": "antagonistic",
    "neutral": "neutral",
    "caution": "caution",
    "use_caution": "caution",
    "compatible": "caution",
    "combination": "caution",
    "avoid_combination": "caution",
    "monitor_combination": "caution",
}


def map_interaction_type(raw_type: str) -> str:
    """Map a raw CSV interaction type to a valid DB enum value.

    Uses exact lookup in ``_INTERACTION_TYPE_MAP`` — no substring matching.
    Unknown types fall back to ``"neutral"``.
    """
    return _INTERACTION_TYPE_MAP.get(str(raw_type).lower().strip(), "neutral")


class InteractionRepository(BaseRepository):
    """Repository for peptide interaction operations."""

    def upsert(self, peptide_id: int, interaction: Dict[str, Any]):
        """Upserts a peptide interaction."""
        secondary_name = interaction['secondary_peptide_name']
        with self.get_cursor() as cur:
            # Check by name first
            cur.execute(
                "SELECT 1 FROM peptide_interactions WHERE peptide_id_1 = %s AND LOWER(peptide_name_2) = LOWER(%s)",
                (peptide_id, secondary_name)
            )
            if cur.fetchone():
                self.log_operation("EXIST_RELATION", "peptide_interactions", 
                    f"Peptide {peptide_id} <-> {secondary_name}")
                return

            try:
                itype = self._map_interaction_type(interaction.get('interaction_type', 'neutral'))
                # Remove ON CONFLICT DO NOTHING — the unique constraint on
                # (peptide_id_1, peptide_id_2) causes ALL rows with NULL
                # peptide_id_2 to share the same key, silently dropping all
                # but the first interaction per peptide.  We rely on the
                # SELECT check above and a partial unique index instead.
                cur.execute(
                    "INSERT INTO peptide_interactions (peptide_id_1, peptide_name_2, interaction_type, description) VALUES (%s, %s, %s, %s)",
                    (peptide_id, secondary_name, itype, interaction['description'])
                )
                self._commit()
                self.log_operation("INSERT_RELATION", "peptide_interactions", 
                    f"Peptide {peptide_id} <-> {secondary_name} ({itype})")
            except Exception as e:
                self._rollback()
                self.log_operation("ERROR_RELATION", "peptide_interactions", str(e))

    def _map_interaction_type(self, raw_type: str) -> str:
        """Maps raw interaction strings to DB enum values: synergistic, antagonistic, neutral, caution."""
        return map_interaction_type(raw_type)

    def get_by_peptide_id(self, peptide_id: int) -> list:
        """Get all interactions for a peptide."""
        return self.execute_all(
            "SELECT * FROM peptide_interactions WHERE peptide_id_1 = %s OR peptide_id_2 = %s",
            (peptide_id, peptide_id)
        )
