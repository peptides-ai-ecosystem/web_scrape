import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional
import json
import logging
import re

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

    def insert_lookup(self, table: str, name: str, **kwargs) -> int:
        """
        Inserts a name into a lookup table if it doesn't exist.
        If it exists, updates columns that are currently NULL with values from kwargs.
        Returns the ID.
        """
        with self.connect().cursor() as cur:
            # 1. Check if it exists and fetch all columns to check for NULLs
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
                    self.conn.commit()
                    logger.info(f"  [LOOKUP_UPDATE] Table {table}: '{name}' (Updated: {', '.join(updates.keys())}, ID: {lookup_id})")
                else:
                    logger.info(f"  [LOOKUP_EXIST] Table {table}: '{name}' (ID: {lookup_id})")
                
                return lookup_id
            
            # 2. Doesn't exist, insert fully
            cols = ["name"] + list(kwargs.keys())
            vals = [name] + list(kwargs.values())
            placeholders = ", ".join(["%s"] * len(cols))
            
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
            cur.execute(sql, vals)
            new_id = cur.fetchone()['id']
            self.conn.commit()
            logger.info(f"  [INSERT_LOOKUP] Table {table}: '{name}' (ID: {new_id})")
            return new_id

    def upsert_research_study(self, study: Dict[str, Any]) -> int:
        """Upserts a research study."""
        title = study.get("title", "Unknown Study")
        url = study.get("url", "")
        abstract = study.get("abstract", "")
        
        with self.connect().cursor() as cur:
            cur.execute("SELECT id, url, abstract FROM research_studies WHERE title = %s", (title,))
            existing = cur.fetchone()
            
            if existing:
                study_id = existing['id']
                updates = {}
                if url and not existing['url']:
                    updates['url'] = url
                if abstract and not existing['abstract']:
                    ### process abstract , remove rest text from .View Study
                    if ".View Study" in abstract:
                        abstract = abstract.split(".View Study")[0]
                    updates['abstract'] = abstract
                
                if updates:
                    set_clause = ", ".join([f"{col} = %s" for col in updates.keys()])
                    sql = f"UPDATE research_studies SET {set_clause} WHERE id = %s"
                    cur.execute(sql, list(updates.values()) + [study_id])
                    self.conn.commit()
                    logger.info(f"  [STUDY_UPDATE] Table research_studies: '{title}' (ID: {study_id})")
                else:
                    logger.info(f"  [STUDY_EXIST] Table research_studies: '{title}' (ID: {study_id})")
                return study_id
            
            cur.execute(
                "INSERT INTO research_studies (title, url, abstract) VALUES (%s, %s, %s) RETURNING id",
                (title, url, abstract)
            )
            new_id = cur.fetchone()['id']
            self.conn.commit()
            logger.info(f"  [INSERT_STUDY] Table research_studies: '{title}' (ID: {new_id})")
            return new_id

    def upsert_citation(self, citation: Dict[str, Any]) -> int:
        """Upserts a citation."""
        title = citation.get("title", "Unknown Citation")
        url = citation.get("url", "")
        abstract = citation.get("abstract", "")
        authors = citation.get("authors", "")
        
        with self.connect().cursor() as cur:
            cur.execute("SELECT id, publication_url, abstract, authors FROM citations WHERE title = %s", (title,))
            existing = cur.fetchone()
            
            if existing:
                citation_id = existing['id']
                updates = {}
                if url and not existing['publication_url']:
                    updates['publication_url'] = url
                if abstract and not existing['abstract']:
                    updates['abstract'] = abstract
                if authors and not existing['authors']:
                    updates['authors'] = authors
                
                if updates:
                    set_clause = ", ".join([f"{col} = %s" for col in updates.keys()])
                    sql = f"UPDATE citations SET {set_clause} WHERE id = %s"
                    cur.execute(sql, list(updates.values()) + [citation_id])
                    self.conn.commit()
                    logger.info(f"  [CITATION_UPDATE] Table citations:(ID: {citation_id})")
                else:
                    logger.info(f"  [CITATION_EXIST] Table citations:(ID: {citation_id})")
                return citation_id
            
            # Note: doi is NOT NULL in schema, providing placeholder if empty
            doi = citation.get("doi")
            if not doi:
                doi = f"none"
            cur.execute(
                "INSERT INTO citations (title, publication_url, abstract, doi, authors) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (title, url, abstract, doi, authors)
            )
            new_id = cur.fetchone()['id']
            self.conn.commit()
            logger.info(f"  [INSERT_CITATION] Table citations:(ID: {new_id})")
            return new_id

    def upsert_peptide_reference(self, peptide_id: int, ref_type: str, ref_id: int):
        """Links a peptide to a research study or citation."""
        table = "peptide_references"
        id_col = "study_id" if ref_type == "study" else "citation_id"
        
        with self.connect().cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {table} WHERE peptide_id = %s AND {id_col} = %s AND reference_type = %s",
                (peptide_id, ref_id, ref_type)
            )
            if cur.fetchone():
                logger.info(f"  [REFERENCE_EXIST] Table peptide_references: Peptide {peptide_id} ({ref_type}) -> {ref_id}")
                return
            
            cur.execute(
                f"INSERT INTO {table} (peptide_id, {id_col}, reference_type) VALUES (%s, %s, %s)",
                (peptide_id, ref_id, ref_type)
            )
            self.conn.commit()
            logger.info(f"  [REFERENCE] Table peptide_references: Linked Peptide {peptide_id} ({ref_type}) -> {ref_id}")

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
                logger.info(f"Inserted new peptide Table peptides: {payload.get('name')} (ID: {peptide_id})")
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
                logger.info(f"Updated Table peptides: {len(updates)} NULL columns for peptide: {payload.get('name')}")
            else:
                logger.info(f"No NULL columns to update for Table peptides: {payload.get('name')}")
            
            return peptide_id

    def get_lookup_id(self, table: str, name: str) -> Optional[int]:
        """Retrieves the ID for a name in a lookup table."""
        with self.connect().cursor() as cur:
            cur.execute(f"SELECT id FROM {table} WHERE name = %s", (name,))
            row = cur.fetchone()
            return row['id'] if row else None

    def get_research_study_id(self, title: str) -> Optional[int]:
        title = title or "Unknown Study"
        with self.connect().cursor() as cur:
            cur.execute("SELECT id FROM research_studies WHERE title = %s", (title,))
            row = cur.fetchone()
            return row['id'] if row else None

    def get_citation_id(self, title: str) -> Optional[int]:
        title = title or "Unknown Citation"
        with self.connect().cursor() as cur:
            cur.execute("SELECT id FROM citations WHERE title = %s", (title,))
            row = cur.fetchone()
            return row['id'] if row else None

    def upsert_interaction(self, peptide_id: int, interaction: Dict[str, Any]):
        """Upserts a peptide interaction."""
        with self.connect().cursor() as cur:
            cur.execute(
                "SELECT 1 FROM peptide_interactions WHERE peptide_id_1 = %s AND LOWER(peptide_name_2) = LOWER(%s)",
                (peptide_id, interaction['secondary_peptide_name'])
            )
            row = cur.fetchone()
            if row:
                logger.info(f"  [RELATION_EXIST] Table peptide_interactions:    Peptide {peptide_id} <-> {interaction['secondary_peptide_name']}")
                return
            else:
                try:
                    itype = self._map_interaction_type(interaction.get('interaction_type', 'neutral'))
                    cur.execute(
                        "INSERT INTO peptide_interactions (peptide_id_1, peptide_name_2, interaction_type, description) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (peptide_id, interaction['secondary_peptide_name'], itype, interaction['description'])
                    )
                    self.conn.commit()
                    if cur.rowcount > 0:
                        logger.info(f"  [RELATION] Table peptide_interactions: Peptide {peptide_id} <-> {interaction['secondary_peptide_name']} ({itype})")
                    else:
                        logger.info(f"  [RELATION_EXIST] Table peptide_interactions (by index): Peptide {peptide_id} <-> {interaction['secondary_peptide_name']}")
                except Exception as e:
                    self.conn.rollback()
                    logger.error(f"Error inserting interaction Table peptide_interactions: {e}")

    def upsert_indication(self, peptide_id: int, indication: Dict[str, Any]):
        """Upserts a research indication."""
        with self.connect().cursor() as cur:
            cur.execute(
                "SELECT id FROM peptide_research_indications WHERE peptide_id = %s AND indication_title = %s",
                (peptide_id, indication['indication_title'])
            )
            row = cur.fetchone()
            if row:
                logger.info(f"  [INDICATION_EXIST] Table peptide_research_indications: Peptide {peptide_id}: '{indication['indication_title']}'")
                return row['id']
            
            cur.execute(
                "INSERT INTO peptide_research_indications (peptide_id, indication_title, effectiveness_tag, description) VALUES (%s, %s, %s, %s) RETURNING id",
                (peptide_id, indication['indication_title'], indication['effectiveness_tag'], indication['description'])
            )
            indication_id = cur.fetchone()['id']
            self.conn.commit()
            logger.info(f"  [INDICATION] Table peptide_research_indications: Added '{indication['indication_title']}' for peptide {peptide_id}")
            return indication_id

    def upsert_protocol(self, peptide_id: int, am_id: int, protocol: Dict[str, Any]) -> int:
        """Upserts a peptide protocol."""
        with self.connect().cursor() as cur:
            cur.execute(
                "SELECT id FROM peptide_protocols WHERE peptide_id = %s AND administration_method_id = %s",
                (peptide_id, am_id)
            )
            row = cur.fetchone()
            if row:
                protocol_id = row['id']
                logger.info(f"  [PROTOCOL_EXIST] Table peptide_protocols: Peptide {peptide_id}: '{protocol['name']}' (ID: {protocol_id})")
                # Update expectations if empty
                cur.execute(
                    "UPDATE peptide_protocols SET expectations = %s WHERE id = %s AND (expectations IS NULL OR expectations = '[]'::jsonb)",
                    (protocol['expectations'], protocol_id)
                )
            else:
                cur.execute(
                    "INSERT INTO peptide_protocols (peptide_id, administration_method_id, name, description, expectations) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (peptide_id, am_id, protocol['name'], protocol.get('description', ''), protocol['expectations'])
                )
                protocol_id = cur.fetchone()['id']
                logger.info(f"  [PROTOCOL] Table peptide_protocols: Created '{protocol['name']}' (ID: {protocol_id}) for peptide {peptide_id}")
            self.conn.commit()
            return protocol_id

    def upsert_reconstitution_step(self, protocol_id: int, step: Dict[str, Any]):
        with self.connect().cursor() as cur:
            cur.execute(
                "SELECT 1 FROM peptide_protocol_reconstitution_steps WHERE protocol_id = %s AND step_number = %s",
                (protocol_id, step['step_number'])
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO peptide_protocol_reconstitution_steps (protocol_id, step_number, description) VALUES (%s, %s, %s)",
                    (protocol_id, step['step_number'], step['description'])
                )
                self.conn.commit()
                logger.info(f"    [DETAIL] Table peptide_protocol_reconstitution_steps: Protocol {protocol_id}: Added reconstitution step {step['step_number']}")

    def upsert_quality_indicator(self, protocol_id: int, indicator: Dict[str, Any]):
        with self.connect().cursor() as cur:
            cur.execute(
                "SELECT 1 FROM protocol_quality_indicators WHERE protocol_id = %s AND indicator_title = %s",
                (protocol_id, indicator['indicator_title'])
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO protocol_quality_indicators (protocol_id, indicator_title, indicator_description) VALUES (%s, %s, %s)",
                    (protocol_id, indicator['indicator_title'], indicator['indicator_description'])
                )
                self.conn.commit()
                logger.info(f"    [DETAIL] Table protocol_quality_indicators: Protocol {protocol_id}: Added quality indicator '{indicator['indicator_title']}'")

    def upsert_protocol_dosage(self, protocol_id: int, dosage: Dict[str, Any]):
        """Upserts a protocol dosage with lookups for dosage_id and schedule_id."""
        amount_str = dosage.get('amount', '')
        freq_str = dosage.get('frequency', '')
        notes = dosage.get('notes', f"Amount: {amount_str}, Freq: {freq_str}")
        
        # 1. Get Dosage ID (only lookup, no create here - done in Group A)
        dosage_id = self._get_or_create_dosage_id(amount_str, create=False)
        
        # 2. Get Schedule ID (only lookup)
        schedule_id = self.get_lookup_id("schedules", freq_str)
        
        if not dosage_id or not schedule_id:
            logger.warning(f"Missing lookup data dosage_id ({dosage_id}) or schedule_id ({schedule_id}) for protocol {protocol_id}")
            return

        with self.connect().cursor() as cur:
            cur.execute(
                "SELECT id FROM protocol_dosages WHERE protocol_id = %s AND dosage_id = %s AND schedule_id = %s",
                (protocol_id, dosage_id, schedule_id)
            )
            row = cur.fetchone()
            if row:
                logger.info(f"    [DOSAGE_EXIST] Table protocol_dosages: Protocol {protocol_id}: dosage_id={dosage_id}, schedule_id={schedule_id}")
                return
            
            cur.execute(
                "INSERT INTO protocol_dosages (protocol_id, dosage_id, schedule_id, is_default, notes) VALUES (%s, %s, %s, %s, %s)",
                (protocol_id, dosage_id, schedule_id, dosage.get('is_default', False), notes)
            )
            self.conn.commit()
            logger.info(f"    [DOSAGE] Table protocol_dosages: Protocol {protocol_id}: Linked dosage {dosage_id} with schedule {schedule_id}")

    def _get_or_create_dosage_id(self, amount_str: str, create: bool = True) -> Optional[int]:
        if not amount_str: return None
        
        # 1. Normalize and Parse: Handle ranges like "10-20mg", "10 - 20 mg", "10 to 20mg"
        # We replace " to " with "-" and remove spaces around the hyphen for standardized storage.
        normalized = amount_str.lower().replace(" to ", "-").strip()
        
        # Regex captures: 
        # Group 1: Numeric part or Range (e.g. "10", "10-20", "10.5-20.5")
        # Group 2: Optional Unit part (e.g. "mg", "ml", "mcg")
        match = re.search(r"([\d\.]+(?:\s*-\s*[\d\.]+)?)\s*([a-zA-Z%/]+)?", normalized)
        
        if match:
            # val: standardize "10 - 20" to "10-20"
            val = match.group(1).replace(" ", "")
            # unit: default to "unit" if not found
            unit = match.group(2) if match.group(2) else "unit"
        else:
            # Fallback: find any number if full pattern fails
            match_num = re.search(r"([\d\.]+)", normalized)
            if match_num:
                val = match_num.group(1)
                unit = "unit"
            else:
                val = "1.0"
                unit = amount_str[:20] if amount_str else "unit"

        with self.connect().cursor() as cur:
            # Strict lookup: Check for exact match of name, amount, and unit 
            cur.execute(
                "SELECT id FROM dosages WHERE name = %s AND amount = %s AND unit = %s", 
                (amount_str[:100], str(val), unit[:20])
            )
            row = cur.fetchone()
            if row:
                if create:
                    logger.info(f"  [DOSAGE_LOOKUP_EXIST] Table dosages: {amount_str} (ID: {row['id']})")
                return row['id']

            if not create:
                return None

            # 3. Create new if missing
            cur.execute(
                "INSERT INTO dosages (name, amount, unit) VALUES (%s, %s, %s) RETURNING id",
                (amount_str[:100], str(val), unit[:20])
            )
            new_id = cur.fetchone()['id']
            self.conn.commit()
            logger.info(f"  [INSERT_DOSAGE] Table dosages: {amount_str} (ID: {new_id})")
            return new_id

    def _map_interaction_type(self, raw_type: str) -> str:
        """Maps raw interaction strings to DB enum values: synergistic, antagonistic, neutral, caution."""
        raw = str(raw_type).lower().strip()
        if any(x in raw for x in ["synergy", "increase", "boost", "positive", "complement"]):
            return "synergistic"
        if any(x in raw for x in ["antagon", "decrease", "block", "negative", "competit"]):
            return "antagonistic"
        if any(x in raw for x in ["caution", "danger", "warning", "risk", "monitor", "combinat", "compatib"]):
            return "caution"
        return "neutral"

    def link_relation(self, table: str, fk1_col: str, fk1_val: int, fk2_col: str, fk2_val: int):
        """Generic method to link two entities in a junction table."""
        with self.connect().cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {table} WHERE {fk1_col} = %s AND {fk2_col} = %s",
                (fk1_val, fk2_val)
            )
            row = cur.fetchone()
            if row:
                logger.info(f"  [LINK_EXIST] Table {table}: {fk1_col}={fk1_val} <-> {fk2_col}={fk2_val}")
                return
            
            cur.execute(
                f"INSERT INTO {table} ({fk1_col}, {fk2_col}) VALUES (%s, %s)",
                (fk1_val, fk2_val)
            )
            self.conn.commit()
            logger.info(f"  [LINK] Linked {table}: {fk1_col}={fk1_val} <-> {fk2_col}={fk2_val}")

    def delete_peptide_data(self, slug: str):
        """Deletes a peptide and its related data (if cascading is not fully set)."""
        with self.connect().cursor() as cur:
            cur.execute("SELECT id FROM peptides WHERE slug = %s", (slug,))
            row = cur.fetchone()
            if not row:
                logger.warning(f"Peptide with slug {slug} not found for deletion.")
                return
            
            peptide_id = row['id']
            
            # Simple manual deletion of top-level relations if cascade isn't on
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
