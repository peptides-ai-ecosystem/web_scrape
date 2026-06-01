"""
IndicationRepositoryV2 — Fixed: peptide_research_indications has no UNIQUE(peptide_id, indication_title).

Uses SELECT → INSERT inside the caller's single transaction.
"""
from typing import Optional
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class IndicationRepositoryV2(BaseRepositoryV2):

    def upsert(self, peptide_id: int, indication: dict) -> Optional[int]:
        existing = self.execute_one(
            "SELECT id FROM peptide_research_indications WHERE peptide_id = %s AND indication_title = %s",
            (peptide_id, indication["indication_title"]),
        )
        if existing:
            self.log_op("EXIST_INDICATION", "peptide_research_indications",
                        f"Peptide {peptide_id}: '{indication['indication_title']}'")
            return existing["id"]

        indication_id = self.execute_returning(
            "INSERT INTO peptide_research_indications (peptide_id, indication_title, effectiveness_tag, description) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (peptide_id, indication["indication_title"],
             indication.get("effectiveness_tag"), indication.get("description")),
        )
        self.log_op("INSERT_INDICATION", "peptide_research_indications",
                    f"Peptide {peptide_id}: '{indication['indication_title']}'")
        return indication_id
