"""
DosageRepositoryV2 — Fixed: dosages has no UNIQUE(name, amount, unit); protocol_dosages
has no UNIQUE(protocol_id, dosage_id, schedule_id).

Both fall back to SELECT → INSERT inside the caller's single transaction.
"""
import re
from typing import Any, Dict, Optional
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class DosageRepositoryV2(BaseRepositoryV2):

    def get_or_create_dosage_id(self, amount_str: str, create: bool = True) -> Optional[int]:
        if not amount_str:
            return None

        normalized = amount_str.lower().replace(" to ", "-").strip()
        match = re.search(r"([\d\.]+(?:\s*-\s*[\d\.]+)?)\s*([a-zA-Z%/]+)?", normalized)
        if match:
            raw_val = match.group(1).replace(" ", "")
            val = raw_val.split("-")[0] if "-" in raw_val else raw_val
            unit = match.group(2) if match.group(2) else "unit"
        else:
            m2 = re.search(r"([\d\.]+)", normalized)
            val = m2.group(1) if m2 else "1.0"
            unit = "unit"

        try:
            val = str(min(float(val), 999999.9999))
        except (ValueError, TypeError):
            val = "1.0"

        name_key = amount_str[:100]
        unit_key = unit[:20]

        existing = self.execute_one(
            "SELECT id FROM dosages WHERE name = %s AND amount = %s AND unit = %s",
            (name_key, val, unit_key),
        )
        if existing:
            self.log_op("EXIST_DOSAGE", "dosages", f"{amount_str} (ID: {existing['id']})")
            return existing["id"]

        if not create:
            return None

        dosage_id = self.execute_returning(
            "INSERT INTO dosages (name, amount, unit) VALUES (%s, %s, %s) RETURNING id",
            (name_key, val, unit_key),
        )
        self.log_op("INSERT_DOSAGE", "dosages", f"{amount_str} (ID: {dosage_id})")
        return dosage_id

    def upsert_protocol_dosage(self, protocol_id: int, dosage: Dict[str, Any]):
        amount_str = dosage.get("amount", "")
        freq_str = dosage.get("frequency", "")
        notes = dosage.get("notes", f"Amount: {amount_str}, Freq: {freq_str}")

        dosage_id = self.get_or_create_dosage_id(amount_str, create=False)
        schedule_id = self._get_schedule_id(freq_str)

        if not dosage_id or not schedule_id:
            self.log_op("WARN_DOSAGE", "protocol_dosages",
                        f"Missing dosage_id={dosage_id} or schedule_id={schedule_id}")
            return

        existing = self.execute_one(
            "SELECT 1 FROM protocol_dosages WHERE protocol_id = %s AND dosage_id = %s AND schedule_id = %s",
            (protocol_id, dosage_id, schedule_id),
        )
        if existing:
            self.log_op("EXIST_PROTO_DOSAGE", "protocol_dosages",
                        f"Protocol {protocol_id}, dosage {dosage_id}, schedule {schedule_id}")
            return

        self.execute_write(
            "INSERT INTO protocol_dosages (protocol_id, dosage_id, schedule_id, is_default, notes) VALUES (%s, %s, %s, %s, %s)",
            (protocol_id, dosage_id, schedule_id, dosage.get("is_default", False), notes),
        )
        self.log_op("INSERT_PROTO_DOSAGE", "protocol_dosages",
                    f"Protocol {protocol_id}, dosage {dosage_id}, schedule {schedule_id}")

    def _get_schedule_id(self, freq_str: str) -> Optional[int]:
        return self.execute_scalar("SELECT id FROM schedules WHERE name = %s", (freq_str,))
