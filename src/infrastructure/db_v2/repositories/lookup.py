"""
LookupRepositoryV2 — Final version with CASE-INSENSITIVE name checks.

Matches indexes like: application_places_name_idx (lower(name))
"""
from typing import Optional
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class LookupRepositoryV2(BaseRepositoryV2):

    def upsert(self, table: str, name: str, **kwargs) -> int:
        """Safe CASE-INSENSITIVE SELECT -> INSERT inside caller's transaction."""
        # Use LOWER() to match functional indexes (e.g., application_places_name_idx)
        existing = self.execute_one(
            f"SELECT id FROM {table} WHERE LOWER(name) = LOWER(%s)", (name,)
        )
        if existing:
            row_id = existing["id"]
            self.log_op("EXIST_LOOKUP", table, f"'{name}' (ID: {row_id})")
            return row_id

        # Insert new row
        cols = ["name"] + list(kwargs.keys())
        vals = [name] + list(kwargs.values())
        placeholders = ", ".join(["%s"] * len(cols))
        
        row_id = self.execute_returning(
            f"INSERT INTO {table} ({', '.join(all_cols) if 'all_cols' in locals() else ', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
            vals,
        )
        self.log_op("INSERT_LOOKUP", table, f"'{name}' (ID: {row_id})")
        return row_id

    def get_id_by_name(self, table: str, name: str) -> Optional[int]:
        return self.execute_scalar(f"SELECT id FROM {table} WHERE LOWER(name) = LOWER(%s)", (name,))
