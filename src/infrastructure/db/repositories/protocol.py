"""Protocol repository for peptide protocol operations."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository


class ProtocolRepository(BaseRepository):
    """Repository for peptide protocol operations."""

    def upsert(self, peptide_id: int, am_id: int, protocol: Dict[str, Any]) -> int:
        """
        Upserts a peptide protocol.
        Matches by peptide, method, and name so different goals
        produce distinct protocols (e.g. "Female HSDD" vs "Male ED").
        Returns the protocol ID.
        """
        # Truncate name to fit VARCHAR(100) constraint
        protocol_name = (protocol.get('name') or '')[:100]
        
        with self.get_cursor() as cur:
            # Check if protocol exists
            cur.execute(
                "SELECT * FROM peptide_protocols WHERE peptide_id = %s AND administration_method_id = %s AND name = %s",
                (peptide_id, am_id, protocol_name)
            )
            row = cur.fetchone()
            
            new_fields = {
                'description': protocol.get('description', ''),
                'expectations': protocol.get('expectations'),
                'quick_start_guide': protocol.get('quick_start_guide'),
                'mechanism_of_action': protocol.get('mechanism_of_action'),
                'key_benefits': protocol.get('key_benefits'),
                'best_timing': (protocol.get('best_timing') or '')[:200],
                'effects_timeline': (protocol.get('effects_timeline') or '')[:200]
            }

            if row:
                protocol_id = row['id']
                self.log_operation("PROTOCOL_EXIST", "peptide_protocols", 
                    f"Peptide {peptide_id}: '{row['name']}' (ID: {protocol_id})")
                
                updates = {}
                for col, val in new_fields.items():
                    existing_val = row.get(col)
                    # For JSONB fields, check for empty lists or '[]'
                    is_empty_jsonb = (existing_val is None or existing_val == [] or existing_val == '[]')
                    if val and (existing_val is None or existing_val == "" or is_empty_jsonb):
                        updates[col] = val
                
                if updates:
                    set_clause = ", ".join([f"{col} = %s" for col in updates.keys()])
                    cur.execute(
                        f"UPDATE peptide_protocols SET {set_clause}, updated_at = NOW() WHERE id = %s",
                        list(updates.values()) + [protocol_id]
                    )
                    self.log_operation("PROTOCOL_UPDATE", "peptide_protocols", 
                        f"Updated {', '.join(updates.keys())} for protocol {protocol_id}")
            else:
                cols = ["peptide_id", "administration_method_id", "name"]
                vals = [peptide_id, am_id, protocol_name]
                
                for col, val in new_fields.items():
                    if val:
                        cols.append(col)
                        vals.append(val)
                
                placeholders = ", ".join(["%s"] * len(cols))
                cur.execute(
                    f"INSERT INTO peptide_protocols ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
                    vals
                )
                protocol_id = cur.fetchone()['id']
                self.log_operation("INSERT_PROTOCOL", "peptide_protocols", 
                    f"Created '{protocol['name']}' (ID: {protocol_id}) for peptide {peptide_id}")
            
            self._commit()
            return protocol_id

    def upsert_reconstitution_step(self, protocol_id: int, step: Dict[str, Any]):
        """Upserts a reconstitution step for a protocol."""
        with self.get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM peptide_protocol_reconstitution_steps WHERE protocol_id = %s AND step_number = %s",
                (protocol_id, step['step_number'])
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO peptide_protocol_reconstitution_steps (protocol_id, step_number, description) VALUES (%s, %s, %s)",
                    (protocol_id, step['step_number'], step['description'])
                )
                self._commit()
                self.log_operation("INSERT_DETAIL", "peptide_protocol_reconstitution_steps", 
                    f"Protocol {protocol_id}: Added reconstitution step {step['step_number']}")

    def upsert_quality_indicator(self, protocol_id: int, indicator: Dict[str, Any]):
        """Upserts a quality indicator for a protocol."""
        with self.get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM protocol_quality_indicators WHERE protocol_id = %s AND indicator_title = %s",
                (protocol_id, indicator['indicator_title'])
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO protocol_quality_indicators (protocol_id, indicator_title, indicator_description) VALUES (%s, %s, %s)",
                    (protocol_id, indicator['indicator_title'], indicator['indicator_description'])
                )
                self._commit()
                self.log_operation("INSERT_DETAIL", "protocol_quality_indicators", 
                    f"Protocol {protocol_id}: Added quality indicator '{indicator['indicator_title']}'")

    def get_by_id(self, protocol_id: int) -> Optional[Dict[str, Any]]:
        """Get protocol by ID."""
        return self.execute_one("SELECT * FROM peptide_protocols WHERE id = %s", (protocol_id,))
