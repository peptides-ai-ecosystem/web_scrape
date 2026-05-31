"""Reference and Lookup repository for linking entities."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository


class ReferenceRepository(BaseRepository):
    """Repository for linking peptides to studies/citations and managing lookups."""

    def upsert_peptide_reference(self, peptide_id: int, ref_type: str, ref_id: int):
        """Links a peptide to a research study or citation."""
        table = "peptide_references"
        id_col = "study_id" if ref_type == "study" else "citation_id"
        
        with self.get_cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {table} WHERE peptide_id = %s AND {id_col} = %s AND reference_type = %s",
                (peptide_id, ref_id, ref_type)
            )
            if cur.fetchone():
                self.log_operation("EXIST_REFERENCE", "peptide_references", 
                    f"Peptide {peptide_id} ({ref_type}) -> {ref_id}")
                return
            
            cur.execute(
                f"INSERT INTO {table} (peptide_id, {id_col}, reference_type) VALUES (%s, %s, %s)",
                (peptide_id, ref_id, ref_type)
            )
            self._commit()
            self.log_operation("INSERT_REFERENCE", "peptide_references", 
                f"Linked Peptide {peptide_id} ({ref_type}) -> {ref_id}")

    def link_entities(self, table: str, fk1_col: str, fk1_val: int, fk2_col: str, fk2_val: int):
        """Generic method to link two entities in a junction table."""
        with self.get_cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {table} WHERE {fk1_col} = %s AND {fk2_col} = %s",
                (fk1_val, fk2_val)
            )
            row = cur.fetchone()
            if row:
                self.log_operation("EXIST_LINK", table, 
                    f"{fk1_col}={fk1_val} <-> {fk2_col}={fk2_val}")
                return

            cur.execute(
                f"INSERT INTO {table} ({fk1_col}, {fk2_col}) VALUES (%s, %s)",
                (fk1_val, fk2_val)
            )
            self._commit()
            self.log_operation("INSERT_LINK", table, 
                f"{fk1_col}={fk1_val} <-> {fk2_col}={fk2_val}")

    def get_references_by_peptide(self, peptide_id: int) -> list:
        """Get all references for a peptide."""
        return self.execute_all(
            "SELECT * FROM peptide_references WHERE peptide_id = %s",
            (peptide_id,)
        )


class LookupRepository(BaseRepository):
    """Repository for lookup table operations (administration_methods, effects, etc.)."""

    def upsert(self, table: str, name: str, **kwargs) -> int:
        """
        Upserts a name into a lookup table if it doesn't exist.
        If it exists, updates columns that are currently NULL with values from kwargs.
        Returns the ID.
        """
        with self.get_cursor() as cur:
            # 1. Check if it exists and fetch all columns
            cur.execute(f"SELECT * FROM {table} WHERE name = %s", (name,))
            existing = cur.fetchone()

            if existing:
                lookup_id = existing['id']
                updates = {}
                for col, val in kwargs.items():
                    # Only update if the field is present in the table,
                    # the input value is not None/empty,
                    # and the existing database value is None or empty.
                    if col in existing and (val is not None and val != ""):
                        curr_val = existing.get(col)
                        if curr_val is None or curr_val == "":
                            updates[col] = val
                
                if updates:
                    set_clause = ", ".join([f"{col} = %s" for col in updates.keys()])
                    sql = f"UPDATE {table} SET {set_clause} WHERE id = %s"
                    params = list(updates.values()) + [lookup_id]
                    cur.execute(sql, params)
                    self._commit()
                    self.log_operation("UPDATE_LOOKUP", table, 
                        f"'{name}' (Updated: {', '.join(updates.keys())}, ID: {lookup_id})")
                else:
                    self.log_operation("EXIST_LOOKUP", table, f"'{name}' (ID: {lookup_id})")
                
                return lookup_id
            
            # 2. Doesn't exist, insert fully
            cols = ["name"] + list(kwargs.keys())
            vals = [name] + list(kwargs.values())
            placeholders = ", ".join(["%s"] * len(cols))
            
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
            cur.execute(sql, vals)
            new_id = cur.fetchone()['id']
            self._commit()
            self.log_operation("INSERT_LOOKUP", table, f"'{name}' (ID: {new_id})")
            return new_id

    def get_id_by_name(self, table: str, name: str) -> Optional[int]:
        """Retrieves the ID for a name in a lookup table."""
        return self.execute_scalar(f"SELECT id FROM {table} WHERE name = %s", (name,))

    def get_by_name(self, table: str, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a row by name from a lookup table."""
        return self.execute_one(f"SELECT * FROM {table} WHERE name = %s", (name,))

    def get_all(self, table: str) -> list:
        """Get all rows from a lookup table."""
        return self.execute_all(f"SELECT * FROM {table}")
