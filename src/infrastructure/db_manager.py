import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DbManager:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = None

    def connect(self):
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
        return self.conn

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()

    def get_peptide_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        with self.connect().cursor() as cur:
            cur.execute("SELECT * FROM peptides WHERE slug = %s", (slug,))
            return cur.fetchone()

    def insert_lookup(self, table: str, name: str) -> int:
        """Inserts a name into a lookup table if it doesn't exist and returns the ID."""
        with self.connect().cursor() as cur:
            cur.execute(f"SELECT id FROM {table} WHERE name = %s", (name,))
            row = cur.fetchone()
            if row:
                return row['id']
            
            cur.execute(f"INSERT INTO {table} (name) VALUES (%s) RETURNING id", (name,))
            new_id = cur.fetchone()['id']
            self.conn.commit()
            return new_id

    def upsert_peptide_fill_nulls(self, payload: Dict[str, Any]) -> int:
        """
        Inserts a peptide or updates its NULL columns if it exists.
        Returns the peptide ID.
        """
        slug = payload.get('slug')
        existing = self.get_peptide_by_slug(slug)

        if not existing:
            # Insert new peptide
            columns = payload.keys()
            values = [payload[col] for col in columns]
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO peptides ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id"
            
            with self.connect().cursor() as cur:
                cur.execute(sql, values)
                peptide_id = cur.fetchone()['id']
                self.conn.commit()
                logger.info(f"Inserted new peptide: {payload.get('name')} (ID: {peptide_id})")
                return peptide_id
        else:
            peptide_id = existing['id']
            updates = {}
            for col, val in payload.items():
                if val and (existing.get(col) is None or existing.get(col) == ""):
                    updates[col] = val
            
            if updates:
                set_clause = ", ".join([f"{col} = %s" for col in updates.keys()])
                sql = f"UPDATE peptides SET {set_clause} WHERE id = %s"
                params = list(updates.values()) + [peptide_id]
                
                with self.connect().cursor() as cur:
                    cur.execute(sql, params)
                    self.conn.commit()
                logger.info(f"Updated {len(updates)} NULL columns for peptide: {payload.get('name')}")
            else:
                logger.info(f"No NULL columns to update for peptide: {payload.get('name')}")
            
            return peptide_id

    def link_relation(self, table: str, peptide_id_col: str, peptide_id: int, relation_id_col: str, relation_id: int, extra_data: Dict[str, Any] = None):
        """Links a peptide to a related entity if the link doesn't exist."""
        sql_check = f"SELECT 1 FROM {table} WHERE {peptide_id_col} = %s AND {relation_id_col} = %s"
        with self.connect().cursor() as cur:
            cur.execute(sql_check, (peptide_id, relation_id))
            if cur.fetchone():
                return # Already linked

            cols = [peptide_id_col, relation_id_col]
            vals = [peptide_id, relation_id]
            if extra_data:
                for k, v in extra_data.items():
                    cols.append(k)
                    vals.append(v)
            
            placeholders = ", ".join(["%s"] * len(cols))
            sql_insert = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
            cur.execute(sql_insert, vals)
            self.conn.commit()

    def delete_peptide_data(self, slug: str):
        """Deletes a peptide and its related data (if cascading is not fully set)."""
        # In a real DB, cascading deletes should be handled by the schema.
        # This is a safety/manual deletion script as requested.
        with self.connect().cursor() as cur:
            cur.execute("SELECT id FROM peptides WHERE slug = %s", (slug,))
            row = cur.fetchone()
            if not row:
                logger.warning(f"Peptide with slug {slug} not found for deletion.")
                return
            
            peptide_id = row['id']
            
            # Simple manual deletion of top-level relations if cascade isn't on
            # Tables from structured.md Group C, D, E, F
            tables = [
                "peptide_protocol_reconstitution_steps", "protocol_application_places", 
                "protocol_quality_indicators", "protocol_dosages", "peptide_protocols",
                "peptide_benefits", "peptide_side_effects", "peptide_interactions",
                "peptide_research_indications", "peptide_references"
            ]
            
            # Note: This is simplified. Some tables depend on protocols, not peptides directly.
            # We would need to fetch protocol IDs first.
            cur.execute("SELECT id FROM peptide_protocols WHERE peptide_id = %s", (peptide_id,))
            protocol_ids = [r['id'] for r in cur.fetchall()]
            
            if protocol_ids:
                p_ids = tuple(protocol_ids)
                if len(p_ids) == 1: p_ids = f"({p_ids[0]})"
                else: p_ids = str(p_ids)
                
                cur.execute(f"DELETE FROM protocol_dosage_benefits WHERE protocol_dosage_id IN (SELECT id FROM protocol_dosages WHERE protocol_id IN {p_ids})")
                cur.execute(f"DELETE FROM protocol_dosage_side_effects WHERE protocol_dosage_id IN (SELECT id FROM protocol_dosages WHERE protocol_id IN {p_ids})")
                cur.execute(f"DELETE FROM protocol_dosages WHERE protocol_id IN {p_ids}")
                cur.execute(f"DELETE FROM protocol_application_places WHERE protocol_id IN {p_ids}")
                cur.execute(f"DELETE FROM protocol_quality_indicators WHERE protocol_id IN {p_ids}")
                cur.execute(f"DELETE FROM peptide_protocol_reconstitution_steps WHERE protocol_id IN {p_ids}")
                cur.execute(f"DELETE FROM peptide_protocols WHERE id IN {p_ids}")

            cur.execute("DELETE FROM peptide_benefits WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM peptide_side_effects WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM peptide_interactions WHERE peptide_id_1 = %s OR peptide_id_2 = %s", (peptide_id, peptide_id))
            cur.execute("DELETE FROM peptide_research_indications WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM peptide_references WHERE peptide_id = %s", (peptide_id,))
            
            cur.execute("DELETE FROM peptides WHERE id = %s", (peptide_id,))
            self.conn.commit()
            logger.info(f"Deleted peptide and related data for slug: {slug}")
