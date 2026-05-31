"""Peptide repository for peptide entity operations."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository


class PeptideRepository(BaseRepository):
    """Repository for peptide entity operations."""

    def get_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get peptide by slug."""
        return self.execute_one("SELECT * FROM peptides WHERE slug = %s", (slug,))

    def get_by_id(self, peptide_id: int) -> Optional[Dict[str, Any]]:
        """Get peptide by ID."""
        return self.execute_one("SELECT * FROM peptides WHERE id = %s", (peptide_id,))

    def upsert_fill_nulls(self, payload: Dict[str, Any]) -> int:
        """
        Inserts a peptide or updates its NULL columns if it exists.
        Returns the peptide ID.
        """
        slug = payload.get('slug')
        existing = self.get_by_slug(slug)

        if not existing:
            # Insert new peptide
            columns = payload.keys()
            values = [payload[col] for col in columns]
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO peptides ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id"
            
            with self.get_cursor() as cur:
                cur.execute(sql, values)
                peptide_id = cur.fetchone()['id']
                self._commit()
                self.log_operation("INSERT_PEPTIDE", "peptides", f"{payload.get('name')} (ID: {peptide_id})")
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
                
                with self.get_cursor() as cur:
                    cur.execute(sql, params)
                    self._commit()
                self.log_operation("UPDATE_PEPTIDE", "peptides", 
                    f"{len(updates)} NULL columns for peptide: {payload.get('name')}")
            else:
                self.log_operation("EXIST_PEPTIDE", "peptides", payload.get('name'))
            
            return peptide_id

    def delete_peptide_cascading(self, slug: str):
        """
        Deletes a peptide and ALL its related data (full cascade).
        This should be called by a service/orchestrator that manages the cascade.
        """
        with self.get_cursor() as cur:
            cur.execute("SELECT id FROM peptides WHERE slug = %s", (slug,))
            row = cur.fetchone()
            if not row:
                self.log_operation("NOT_FOUND", "peptides", f"slug='{slug}'")
                return

            peptide_id = row['id']

            # --- Protocol subtree ---
            cur.execute("SELECT id FROM peptide_protocols WHERE peptide_id = %s", (peptide_id,))
            protocol_ids = [r['id'] for r in cur.fetchall()]

            if protocol_ids:
                # protocol_dosages subtree
                cur.execute(
                    "SELECT id FROM protocol_dosages WHERE protocol_id = ANY(%s)",
                    (protocol_ids,)
                )
                dosage_ids = [r['id'] for r in cur.fetchall()]

                if dosage_ids:
                    cur.execute("DELETE FROM protocol_dosage_benefits WHERE protocol_dosage_id = ANY(%s)", (dosage_ids,))
                    cur.execute("DELETE FROM protocol_dosage_side_effects WHERE protocol_dosage_id = ANY(%s)", (dosage_ids,))
                    cur.execute("DELETE FROM protocol_dosages WHERE id = ANY(%s)", (dosage_ids,))

                # peptide_research_indication_studies linked via protocol_id
                cur.execute("DELETE FROM peptide_research_indication_studies WHERE protocol_id = ANY(%s)", (protocol_ids,))
                cur.execute("DELETE FROM protocol_application_places WHERE protocol_id = ANY(%s)", (protocol_ids,))
                cur.execute("DELETE FROM protocol_quality_indicators WHERE protocol_id = ANY(%s)", (protocol_ids,))
                cur.execute("DELETE FROM peptide_protocol_reconstitution_steps WHERE protocol_id = ANY(%s)", (protocol_ids,))
                cur.execute("DELETE FROM peptide_protocols WHERE id = ANY(%s)", (protocol_ids,))
                self.log_operation("DELETE_CASCADE", "peptide_protocols", 
                    f"{len(protocol_ids)} protocol(s) for peptide {peptide_id}")

            # --- Research indications subtree ---
            cur.execute("SELECT id FROM peptide_research_indications WHERE peptide_id = %s", (peptide_id,))
            indication_ids = [r['id'] for r in cur.fetchall()]

            if indication_ids:
                cur.execute("DELETE FROM peptide_research_indication_studies WHERE indication_id = ANY(%s)", (indication_ids,))
                cur.execute("DELETE FROM peptide_research_indications WHERE id = ANY(%s)", (indication_ids,))
                self.log_operation("DELETE_CASCADE", "peptide_research_indications", f"{len(indication_ids)} indication(s)")

            # --- Direct peptide relations ---
            cur.execute("DELETE FROM peptide_benefits WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM peptide_side_effects WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM peptide_interactions WHERE peptide_id_1 = %s OR peptide_id_2 = %s", (peptide_id, peptide_id))
            cur.execute("DELETE FROM peptide_references WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM peptide_graph WHERE peptide_id = %s", (peptide_id,))

            # --- Pricing / vendor relations ---
            cur.execute("DELETE FROM pepti_price_price_history WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM pepti_price_vendor_pricing WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM pepti_price_watchlist WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM vendor_peptides WHERE peptide_id = %s", (peptide_id,))

            # --- Wiki / analytics relations ---
            cur.execute("DELETE FROM wiki_peptide_analytics WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM wiki_trending_peptides WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM wiki_user_peptide_feedback_answers WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM wiki_user_peptide_question_answers WHERE peptide_id = %s", (peptide_id,))
            cur.execute("DELETE FROM wiki_referral_clicks WHERE peptide_id = %s", (peptide_id,))

            # --- SDS / other relations ---
            cur.execute("DELETE FROM sds_compounds WHERE peptide_id = %s", (peptide_id,))

            # --- Finally delete the peptide itself ---
            cur.execute("DELETE FROM peptides WHERE id = %s", (peptide_id,))
            self._commit()
            self.log_operation("DELETE_FULL", "peptides", f"slug='{slug}' (id={peptide_id}) and all related data")
