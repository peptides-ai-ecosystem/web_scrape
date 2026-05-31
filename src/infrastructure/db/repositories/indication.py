"""Indication repository for research indication operations."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository


class IndicationRepository(BaseRepository):
    """Repository for peptide research indication operations."""

    def upsert(self, peptide_id: int, indication: Dict[str, Any]) -> int:
        """
        Upserts a research indication.
        Returns the indication ID.
        """
        with self.get_cursor() as cur:
            cur.execute(
                "SELECT id FROM peptide_research_indications WHERE peptide_id = %s AND indication_title = %s",
                (peptide_id, indication['indication_title'])
            )
            row = cur.fetchone()
            if row:
                self.log_operation("EXIST_INDICATION", "peptide_research_indications", 
                    f"Peptide {peptide_id}: '{indication['indication_title']}'")
                return row['id']
            
            cur.execute(
                "INSERT INTO peptide_research_indications (peptide_id, indication_title, effectiveness_tag, description) VALUES (%s, %s, %s, %s) RETURNING id",
                (peptide_id, indication['indication_title'], indication['effectiveness_tag'], indication['description'])
            )
            indication_id = cur.fetchone()['id']
            self._commit()
            self.log_operation("INSERT_INDICATION", "peptide_research_indications", 
                f"Added '{indication['indication_title']}' for peptide {peptide_id}")
            return indication_id

    def get_by_peptide_id(self, peptide_id: int) -> list:
        """Get all indications for a peptide."""
        return self.execute_all(
            "SELECT * FROM peptide_research_indications WHERE peptide_id = %s",
            (peptide_id,)
        )

    def get_by_id(self, indication_id: int) -> Optional[Dict[str, Any]]:
        """Get indication by ID."""
        return self.execute_one(
            "SELECT * FROM peptide_research_indications WHERE id = %s",
            (indication_id,)
        )
