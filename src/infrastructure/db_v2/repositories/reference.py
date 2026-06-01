"""
ReferenceRepositoryV2 — Fixed after schema inspection.

None of these junction tables have explicit UNIQUE constraints:
  - peptide_references
  - peptide_benefits
  - peptide_side_effects
  - protocol_application_places

All use SELECT → INSERT inside the caller's single transaction (safe, no commit).
"""
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class ReferenceRepositoryV2(BaseRepositoryV2):

    def upsert_peptide_reference(self, peptide_id: int, ref_type: str, ref_id: int):
        """Link a peptide to a study or citation (idempotent)."""
        id_col = "study_id" if ref_type == "study" else "citation_id"
        existing = self.execute_one(
            f"SELECT 1 FROM peptide_references WHERE peptide_id = %s AND {id_col} = %s AND reference_type = %s",
            (peptide_id, ref_id, ref_type),
        )
        if existing:
            self.log_op("EXIST_REF", "peptide_references",
                        f"Peptide {peptide_id} ({ref_type}) -> {ref_id}")
            return

        self.execute_write(
            f"INSERT INTO peptide_references (peptide_id, {id_col}, reference_type) VALUES (%s, %s, %s)",
            (peptide_id, ref_id, ref_type),
        )
        self.log_op("INSERT_REF", "peptide_references",
                    f"Peptide {peptide_id} ({ref_type}) -> {ref_id}")

    def link_entities(self, table: str, fk1_col: str, fk1_val: int,
                      fk2_col: str, fk2_val: int):
        """Generic junction-table link (idempotent via SELECT guard)."""
        existing = self.execute_one(
            f"SELECT 1 FROM {table} WHERE {fk1_col} = %s AND {fk2_col} = %s",
            (fk1_val, fk2_val),
        )
        if existing:
            self.log_op("EXIST_LINK", table,
                        f"{fk1_col}={fk1_val} <-> {fk2_col}={fk2_val}")
            return

        self.execute_write(
            f"INSERT INTO {table} ({fk1_col}, {fk2_col}) VALUES (%s, %s)",
            (fk1_val, fk2_val),
        )
        self.log_op("INSERT_LINK", table,
                    f"{fk1_col}={fk1_val} <-> {fk2_col}={fk2_val}")
