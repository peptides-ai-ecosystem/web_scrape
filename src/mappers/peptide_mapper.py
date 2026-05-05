import re
from typing import Any, Dict
from src.mappers.base_mapper import BaseMapper


class PeptideMapper(BaseMapper):
    """
    Responsible for mapping raw data into the 'peptides' table payload.
    """

    def map(self, row: Dict[str, Any]) -> Dict[str, Any]:
        raw_name = row.get("Peptide_Name", "").strip()
        full_name = row.get("Full_Name", "").strip()

        # Generate a slug from name
        slug = re.sub(r'[^a-z0-9]+', '-', raw_name.lower()).strip('-')

        return {
            "name": raw_name,
            "slug": slug,
            "synonyms": full_name,
            "overview": row.get("overview_what_is_bpc-157", "").strip() or row.get(f"overview_what_is_{slug.replace('-', '_')}", "").strip(),
            "mechanism_of_action": row.get("overview_mechanism_of_action", "").strip(),
            "sequence": row.get("molecular_information_amino_acid_sequence", "").strip(),
            "cycle_duration": row.get("cycle", "").strip(),
            "storage_temperature": row.get("storage", "").strip(),
            "fda_approval_status": "",  # Can be mapped dynamically
            "wada_status": "", # Usually prohibited, should be parsed dynamically if text says
            # stop_signs mapping from 'side_effects_and_safety_when_to_stop_X'
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
