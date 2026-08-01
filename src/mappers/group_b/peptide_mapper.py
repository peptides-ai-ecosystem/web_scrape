import json
import re
from typing import Any, Dict
from src.mappers.base import BaseMapper

class PeptideMapper(BaseMapper):
    """Group B: Maps the central peptide record."""

    def map(self, row: Dict[str, Any]) -> Dict[str, Any]:
        raw_name = (row.get("Peptide_Name") or "").strip()
        full_name = (row.get("Full_Name") or "").strip()

        # Generate a slug from name
        slug = re.sub(r'[^a-z0-9]+', '-', raw_name.lower()).strip('-')

        # Dynamically determine the overview column if name-specific
        overview = (row.get(f"overview_what_is_{slug.replace('-', '_')}") or "").strip()
        if not overview:
            # Fallback to search any column starting with overview_what_is
            for k, v in row.items():
                if k and isinstance(k, str) and k.startswith("overview_what_is_") and v and isinstance(v, str) and v.strip():
                    overview = v.strip()
                    break

        fda_status = (row.get("fda_approval_status") or "").strip()
        wada_status = (row.get("wada_status") or "").strip()

        return {
            "name": raw_name,
            "slug": slug,
            "synonyms": full_name,
            "overview": overview,
            "mechanism_of_action": (row.get("overview_mechanism_of_action") or "").strip(),
            "sequence": (row.get("molecular_information_amino_acid_sequence") or "").strip(),
            "molecular_type": (row.get("molecular_information_type") or "").strip(),
            "molecular_length": (row.get("molecular_information_length") or "").strip(),
            "molecular_weight": (row.get("molecular_information_weight") or "").strip(),
            "cycle_duration": (row.get("cycle") or "").strip(),
            "storage_temperature": (row.get("storage") or "").strip(),
            "fda_approval_status": fda_status if fda_status else None,
            "wada_status": wada_status if wada_status else None,
            "contraindications": self._extract_contraindications(row),
            "stop_signs": self._extract_stop_signs(row),
            "key_information": (row.get("overview_key_benefits") or "").strip()
        }

    def _extract_contraindications(self, row: Dict[str, Any]) -> str:
        """Extract what_to_expect_{1..n} columns as a key:value JSON object.

        CSV values look like "Week 1-2: Minimal noticeable effects..." so the
        period before the colon becomes the key and the statement the value.
        Values without a colon fall back to a "Note N" key.
        """
        expectations = {}
        for i in range(1, 6):
            value = (row.get(f"what_to_expect_{i}") or "").strip()
            if not value:
                continue
            if ":" in value:
                key, _, statement = value.partition(":")
                key = key.strip()
                statement = statement.strip()
            else:
                key, statement = f"Note {len(expectations) + 1}", value.strip()
            if key and statement:
                expectations[key] = statement
        return json.dumps(expectations) if expectations else json.dumps([])

    def _extract_stop_signs(self, row: Dict[str, Any]) -> str:
        """Extract side_effects_and_safety_when_to_stop_{1..n} columns as a key:value JSON object.

        The CSV suffix (1, 2, ... n) becomes the key ("stop_sign_number") and
        the statement becomes the value, preserving CSV column order.
        Example: {"1": "Severe headache", "2": "Nausea", "3": "Persistent fatigue"}
        """
        prefix = "side_effects_and_safety_when_to_stop_"
        stop_items = {}

        for key, value in row.items():
            if isinstance(key, str) and key.startswith(prefix) and isinstance(value, str):
                trimmed = value.strip()
                if trimmed:
                    suffix = key[len(prefix):].strip()
                    stop_items[suffix] = trimmed

        return json.dumps(stop_items) if stop_items else json.dumps([])
