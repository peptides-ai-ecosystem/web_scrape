"""
ProtocolRepositoryV2 — Fixed: peptide_protocols, peptide_protocol_reconstitution_steps,
and protocol_quality_indicators have NO unique constraints beyond their PKs.

Falls back to SELECT → INSERT inside the caller's single transaction.
"""
from typing import Any, Dict, Optional
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class ProtocolRepositoryV2(BaseRepositoryV2):

    def upsert(self, peptide_id: int, am_id: int, protocol: Dict[str, Any]) -> int:
        protocol_name = (protocol.get("name") or "")[:100]

        existing = self.execute_one(
            "SELECT * FROM peptide_protocols WHERE peptide_id = %s AND administration_method_id = %s",
            (peptide_id, am_id),
        )

        new_fields = {
            "description":         protocol.get("description", ""),
            "expectations":        protocol.get("expectations"),
            "quick_start_guide":   protocol.get("quick_start_guide"),
            "mechanism_of_action": protocol.get("mechanism_of_action"),
            "key_benefits":        protocol.get("key_benefits"),
            "best_timing":         (protocol.get("best_timing") or "")[:200],
            "effects_timeline":    (protocol.get("effects_timeline") or "")[:200],
        }

        if existing:
            protocol_id = existing["id"]
            updates = {}
            for col, val in new_fields.items():
                existing_val = existing.get(col)
                is_empty = existing_val is None or existing_val == "" or existing_val == [] or existing_val == "[]"
                if val and is_empty:
                    updates[col] = val
            if updates:
                set_clause = ", ".join([f"{col} = %s" for col in updates]) + ", updated_at = NOW()"
                self.execute_write(
                    f"UPDATE peptide_protocols SET {set_clause} WHERE id = %s",
                    list(updates.values()) + [protocol_id],
                )
            self.log_op("UPSERT_PROTOCOL", "peptide_protocols",
                        f"Peptide {peptide_id}/method {am_id} -> ID {protocol_id}")
            return protocol_id

        cols = ["peptide_id", "administration_method_id", "name"]
        vals = [peptide_id, am_id, protocol_name]
        for col, val in new_fields.items():
            if val:
                cols.append(col)
                vals.append(val)

        protocol_id = self.execute_returning(
            f"INSERT INTO peptide_protocols ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))}) RETURNING id",
            vals,
        )
        self.log_op("INSERT_PROTOCOL", "peptide_protocols",
                    f"Peptide {peptide_id}/method {am_id} -> ID {protocol_id}")
        return protocol_id

    def upsert_reconstitution_step(self, protocol_id: int, step: Dict[str, Any]):
        existing = self.execute_one(
            "SELECT 1 FROM peptide_protocol_reconstitution_steps WHERE protocol_id = %s AND step_number = %s",
            (protocol_id, step["step_number"]),
        )
        if not existing:
            self.execute_write(
                "INSERT INTO peptide_protocol_reconstitution_steps (protocol_id, step_number, description) VALUES (%s, %s, %s)",
                (protocol_id, step["step_number"], step.get("description")),
            )
            self.log_op("INSERT_RECON_STEP", "peptide_protocol_reconstitution_steps",
                        f"Protocol {protocol_id}: step {step['step_number']}")

    def upsert_quality_indicator(self, protocol_id: int, indicator: Dict[str, Any]):
        existing = self.execute_one(
            "SELECT 1 FROM protocol_quality_indicators WHERE protocol_id = %s AND indicator_title = %s",
            (protocol_id, indicator["indicator_title"]),
        )
        if not existing:
            self.execute_write(
                "INSERT INTO protocol_quality_indicators (protocol_id, indicator_title, indicator_description) VALUES (%s, %s, %s)",
                (protocol_id, indicator["indicator_title"], indicator.get("indicator_description")),
            )
            self.log_op("INSERT_QI", "protocol_quality_indicators",
                        f"Protocol {protocol_id}: '{indicator['indicator_title']}'")
