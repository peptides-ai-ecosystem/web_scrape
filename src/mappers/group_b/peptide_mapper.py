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
            "cycle_duration": (row.get("cycle") or "").strip(),
            "storage_temperature": (row.get("storage") or "").strip(),
            "fda_approval_status": fda_status if fda_status else None,
            "wada_status": wada_status if wada_status else None,
            "stop_signs": self._extract_stop_signs(row),
            "key_information": (row.get("overview_key_benefits") or "").strip()
        }

    def _extract_stop_signs(self, row: Dict[str, Any]) -> list[str]:
        prefix = "side_effects_and_safety_when_to_stop_"
        stop_items = []

        for key, value in row.items():
            if isinstance(key, str) and key.startswith(prefix) and isinstance(value, str):
                trimmed = value.strip()
                if trimmed:
                    suffix = key[len(prefix):]
                    stop_items.append((suffix, trimmed))

        def sort_key(item: tuple[str, str]) -> tuple[int | str, str]:
            suffix, _ = item
            try:
                return (int(suffix), suffix)
            except ValueError:
                return (float('inf'), suffix)

        stop_items.sort(key=sort_key)
        return [value for _, value in stop_items]
