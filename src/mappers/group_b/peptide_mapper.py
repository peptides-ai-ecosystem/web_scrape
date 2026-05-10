import re
from typing import Any, Dict
from src.mappers.base import BaseMapper

class PeptideMapper(BaseMapper):
    """Group B: Maps the central peptide record."""

    def map(self, row: Dict[str, Any]) -> Dict[str, Any]:
        raw_name = row.get("Peptide_Name", "").strip()
        full_name = row.get("Full_Name", "").strip()

        # Generate a slug from name
        slug = re.sub(r'[^a-z0-9]+', '-', raw_name.lower()).strip('-')

        # Dynamically determine the overview column if name-specific
        overview = row.get(f"overview_what_is_{slug.replace('-', '_')}", "").strip()
        if not overview:
            # Fallback to search any column starting with overview_what_is
            for k, v in row.items():
                if k.startswith("overview_what_is_") and v.strip():
                    overview = v.strip()
                    break

        fda_status = row.get("fda_approval_status", "").strip()
        wada_status = row.get("wada_status", "").strip()

        return {
            "name": raw_name,
            "slug": slug,
            "synonyms": full_name,
            "overview": overview,
            "mechanism_of_action": row.get("overview_mechanism_of_action", "").strip(),
            "sequence": row.get("molecular_information_amino_acid_sequence", "").strip(),
            "cycle_duration": row.get("cycle", "").strip(),
            "storage_temperature": row.get("storage", "").strip(),
            "fda_approval_status": fda_status if fda_status else None,
            "wada_status": wada_status if wada_status else None,
            "stop_signs": self._extract_stop_signs(row),
            "key_information": row.get("overview_key_benefits", "").strip()
        }

    def _extract_stop_signs(self, row: Dict[str, Any]) -> str:
        stops = []
        for i in range(1, 10):
            val = row.get(f"side_effects_and_safety_when_to_stop_{i}", "").strip()
            if val:
                stops.append(val)
        return ", ".join(stops)
