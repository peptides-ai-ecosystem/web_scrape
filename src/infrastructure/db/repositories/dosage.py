"""Dosage repository for dosage and protocol dosage operations."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository
import re


class DosageRepository(BaseRepository):
    """Repository for dosage and protocol dosage operations."""

    def get_or_create_dosage_id(self, amount_str: str, create: bool = True) -> Optional[int]:
        """
        Get or create a dosage ID.
        
        Normalizes and parses dosage strings (e.g., "10-20mg", "10 - 20 mg", "10 to 20mg").
        """
        if not amount_str:
            return None
        
        # Normalize and Parse: Handle ranges like "10-20mg", "10 - 20 mg", "10 to 20mg"
        normalized = amount_str.lower().replace(" to ", "-").strip()
        
        # Regex captures: 
        # Group 1: Numeric part or Range (e.g. "10", "10-20", "10.5-20.5")
        # Group 2: Optional Unit part (e.g. "mg", "ml", "mcg")
        match = re.search(r"([\d\.]+(?:\s*-\s*[\d\.]+)?)\s*([a-zA-Z%/]+)?", normalized)
        
        if match:
            # Extract numeric part; if a range like "10-20" is present, take the first number
            raw_val = match.group(1).replace(" ", "")
            if "-" in raw_val:
                val = raw_val.split("-")[0]
            else:
                val = raw_val
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
        
        # Convert to float and cap at maximum NUMERIC(10,4) value
        try:
            val_float = float(val)
            val_float = min(val_float, 999999.9999)
            val = str(val_float)
        except (ValueError, TypeError):
            val = "1.0"

        with self.get_cursor() as cur:
            # Strict lookup: Check for exact match of name, amount, and unit 
            cur.execute(
                "SELECT id FROM dosages WHERE name = %s AND amount = %s AND unit = %s", 
                (amount_str[:100], str(val), unit[:20])
            )
            row = cur.fetchone()
            if row:
                if create:
                    self.log_operation("EXIST_DOSAGE", "dosages", f"{amount_str} (ID: {row['id']})")
                return row['id']

            if not create:
                return None

            # Create new if missing
            cur.execute(
                "INSERT INTO dosages (name, amount, unit) VALUES (%s, %s, %s) RETURNING id",
                (amount_str[:100], str(val), unit[:20])
            )
            new_id = cur.fetchone()['id']
            self._commit()
            self.log_operation("INSERT_DOSAGE", "dosages", f"{amount_str} (ID: {new_id})")
            return new_id

    def upsert_protocol_dosage(self, protocol_id: int, dosage: Dict[str, Any]):
        """Upserts a protocol dosage with lookups for dosage_id and schedule_id."""
        amount_str = dosage.get('amount', '')
        freq_str = dosage.get('frequency', '')
        notes = dosage.get('notes', f"Amount: {amount_str}, Freq: {freq_str}")
        
        # 1. Get Dosage ID (only lookup, no create here)
        dosage_id = self.get_or_create_dosage_id(amount_str, create=False)
        
        # 2. Get Schedule ID (lookup)
        schedule_id = self._get_schedule_id(freq_str)
        
        if not dosage_id or not schedule_id:
            self.log_operation("WARNING", "protocol_dosages", 
                f"Missing lookup data dosage_id ({dosage_id}) or schedule_id ({schedule_id})")
            return

        with self.get_cursor() as cur:
            cur.execute(
                "SELECT id FROM protocol_dosages WHERE protocol_id = %s AND dosage_id = %s AND schedule_id = %s",
                (protocol_id, dosage_id, schedule_id)
            )
            row = cur.fetchone()
            if row:
                self.log_operation("EXIST_DOSAGE", "protocol_dosages", 
                    f"Protocol {protocol_id}: dosage_id={dosage_id}, schedule_id={schedule_id}")
                return
            
            cur.execute(
                "INSERT INTO protocol_dosages (protocol_id, dosage_id, schedule_id, is_default, notes) VALUES (%s, %s, %s, %s, %s)",
                (protocol_id, dosage_id, schedule_id, dosage.get('is_default', False), notes)
            )
            self._commit()
            self.log_operation("INSERT_DOSAGE", "protocol_dosages", 
                f"Protocol {protocol_id}: Linked dosage {dosage_id} with schedule {schedule_id}")

    def _get_schedule_id(self, freq_str: str) -> Optional[int]:
        """Get schedule ID by frequency name."""
        return self.execute_scalar("SELECT id FROM schedules WHERE name = %s", (freq_str,))

    def get_by_protocol_id(self, protocol_id: int) -> list:
        """Get all dosages for a protocol."""
        return self.execute_all(
            "SELECT * FROM protocol_dosages WHERE protocol_id = %s",
            (protocol_id,)
        )
