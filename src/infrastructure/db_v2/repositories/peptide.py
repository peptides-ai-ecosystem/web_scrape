"""
PeptideRepositoryV2 — Final version with CASE-INSENSITIVE name checks.

Matches: peptides_name_unique_idx (lower(name))
"""
from typing import Any, Dict, Optional
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class PeptideRepositoryV2(BaseRepositoryV2):

    def get_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        return self.execute_one("SELECT * FROM peptides WHERE slug = %s", (slug,))

    def upsert_fill_nulls(self, payload: Dict[str, Any]) -> int:
        """Safe CASE-INSENSITIVE peptide upsert."""
        slug = payload.get("slug")
        name = payload.get("name")
        
        # 1. Check if exists (check by slug OR case-insensitive name)
        existing = self.get_by_slug(slug)
        if not existing and name:
            existing = self.execute_one("SELECT * FROM peptides WHERE LOWER(name) = LOWER(%s)", (name,))
        
        if not existing:
            columns = list(payload.keys())
            values = [payload[col] for col in columns]
            placeholders = ", ".join(["%s"] * len(columns))
            
            sql_insert = f"INSERT INTO peptides ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id"
            peptide_id = self.execute_returning(sql_insert, values)
            self.log_op("INSERT_PEPTIDE", "peptides", f"{name} (ID: {peptide_id})")
            return peptide_id

        # 3. Partial UPDATE
        peptide_id = existing["id"]
        updates = {
            col: val
            for col, val in payload.items()
            if val and (existing.get(col) is None or str(existing.get(col)).strip() == "")
        }

        if updates:
            set_clause = ", ".join([f"{col} = %s" for col in updates])
            sql_update = f"UPDATE peptides SET {set_clause} WHERE id = %s"
            self.execute_write(sql_update, list(updates.values()) + [peptide_id])
            self.log_op("UPDATE_PEPTIDE", "peptides", f"Updated {len(updates)} cols for '{name}'")
        else:
            self.log_op("EXIST_PEPTIDE", "peptides", name)

        return peptide_id
