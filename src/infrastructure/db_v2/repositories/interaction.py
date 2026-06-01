"""
InteractionRepositoryV2 — Final version with data hygiene.

Maps 'interact' to 'neutral' to satisfy DB enum constraints.
Matches index: peptide_interactions_unique_pair.
"""
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class InteractionRepositoryV2(BaseRepositoryV2):

    def upsert(self, peptide_id: int, interaction: dict) -> None:
        """
        Ensures interaction doesn't violate functional index or enum constraints.
        """
        # Enum Hygiene: Map common placeholders to valid DB enum values
        raw_type = interaction.get("type", "neutral").lower()
        valid_types = {"synergistic", "antagonistic", "neutral", "caution"}
        itype = raw_type if raw_type in valid_types else "neutral"
        
        name2 = interaction["secondary_peptide_name"]
        
        # 1. Search for peptide_id_2 to avoid (-1, id1) collisions in index
        peptide_id_2 = self.execute_scalar(
            "SELECT id FROM peptides WHERE LOWER(name) = LOWER(%s)", (name2,)
        )
        
        id1 = peptide_id
        id2_for_idx = peptide_id_2 if peptide_id_2 is not None else -1
        
        lower_bound = min(id1, id2_for_idx)
        upper_bound = max(id1, id2_for_idx)

        # 2. Functional Index Check
        existing = self.execute_one(
            """
            SELECT id FROM peptide_interactions 
            WHERE LEAST(peptide_id_1, COALESCE(peptide_id_2, -1)) = %s 
              AND GREATEST(peptide_id_1, COALESCE(peptide_id_2, -1)) = %s
            """,
            (lower_bound, upper_bound)
        )
        
        if existing:
            self.log_op("EXIST_INTERACTION", "peptide_interactions", f"Pair ({id1}, {id2_for_idx})")
            return

        # 3. INSERT
        sql = """
            INSERT INTO peptide_interactions (peptide_id_1, peptide_id_2, peptide_name_2, interaction_type, description)
            VALUES (%s, %s, %s, %s, %s)
        """
        self.execute_write(sql, (id1, peptide_id_2, name2, itype, interaction.get("description", "")))
        self.log_op("INSERT_INTERACTION", "peptide_interactions", f"P1: {id1}, P2: {id2_for_idx}")
