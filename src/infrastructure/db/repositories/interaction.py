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
        """Upserts a peptide interaction.

        If the interaction dict contains a ``secondary_peptide_id``
        (resolved by the caller via a DB lookup), the relationship is
        stored with both ``peptide_id_1`` and ``peptide_id_2`` —
        otherwise it falls back to ``peptide_name_2`` only.

        When ``secondary_peptide_id`` is available but an existing row
        was previously stored with only ``peptide_name_2`` (ID was not
        yet resolved), that row is **upgraded** with the resolved ID
        instead of being skipped or duplicated.
        """
        secondary_name = interaction.get('secondary_peptide_name', '')
        secondary_id = interaction.get('secondary_peptide_id')
        with self.get_cursor() as cur:
            # Check for existing — prefer peptide_id_2 match when available
            if secondary_id:
                cur.execute(
                    "SELECT id FROM peptide_interactions WHERE peptide_id_1 = %s AND peptide_id_2 = %s",
                    (peptide_id, secondary_id)
                )
                row = cur.fetchone()
                if row:
                    self.log_operation("EXIST_RELATION", "peptide_interactions",
                        f"Peptide {peptide_id} <-> {secondary_id}")
                    return
                # Also check by name — row may exist without peptide_id_2
                cur.execute(
                    "SELECT id FROM peptide_interactions WHERE peptide_id_1 = %s AND LOWER(peptide_name_2) = LOWER(%s)",
                    (peptide_id, secondary_name)
                )
                name_row = cur.fetchone()
                if name_row:
                    # Upgrade: add the resolved ID to the existing row
                    cur.execute(
                        "UPDATE peptide_interactions SET peptide_id_2 = %s WHERE id = %s",
                        (secondary_id, name_row['id'])
                    )
                    self._commit()
                    self.log_operation("UPDATE_RELATION", "peptide_interactions",
                        f"Peptide {peptide_id} <-> {secondary_name} (added ID {secondary_id})")
                    return
            else:
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
                if secondary_id:
                    cur.execute(
                        "INSERT INTO peptide_interactions (peptide_id_1, peptide_id_2, peptide_name_2, interaction_type, description) VALUES (%s, %s, %s, %s, %s)",
                        (peptide_id, secondary_id, secondary_name, itype, interaction.get('description'))
                    )
                else:
                    cur.execute(
                        "INSERT INTO peptide_interactions (peptide_id_1, peptide_name_2, interaction_type, description) VALUES (%s, %s, %s, %s)",
                        (peptide_id, secondary_name, itype, interaction.get('description'))
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
