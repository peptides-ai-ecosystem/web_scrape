import json
import re
from typing import Any

from app.services.sync.base import BaseMapper


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def _clean(value: Any) -> str:
    """CSV hero facts are written as "value (extra)"; an empty extra leaves " ()"."""
    text = str(value or "").strip()
    return text[:-2].rstrip() if text.endswith("()") else text


# pep-pedia has no fixed schema: these are the column names its facts, quick-start
# card and sections have produced (hero facts and quick_guide_* are lower-cased
# labels). A label that is not found leaves the column empty; nothing is guessed.
_SINGLE = {
    "effect_onset": ("effect_onset", "onset", "onset_of_action", "quick_guide_onset", "time_to_effect"),
    "break_period": ("break_period", "break", "off_period", "rest_period", "quick_guide_break"),
    "required_materials": ("required_materials", "materials", "materials_needed", "supplies", "what_you_need"),
}
_HALF_LIFE = ("half_life", "quick_guide_half_life", "pharmacokinetics_half_life")
_MULTI = {  # numbered columns joined one per line
    "safety_guidelines": ("safety_guidelines", "side_effects_and_safety_safety_guidelines"),
    "quality_checks": ("quality_checks", "quality_indicators"),
}
_HALF_LIFE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(?:\d+(?:\.\d+)?)?\s*(min|h|d)[a-z]*", re.IGNORECASE)
_UNITS = {"min": "minutes", "h": "hours", "d": "days"}


class PeptideMapper(BaseMapper):
    """Group B: Maps the central peptide record."""

    def map(self, row: dict[str, Any]) -> dict[str, Any]:
        raw_name = (row.get("Peptide_Name") or "").strip()
        full_name = (row.get("Full_Name") or "").strip()

        # Generate a slug from name
        slug = re.sub(r"[^a-z0-9]+", "-", raw_name.lower()).strip("-")

        # Dynamically determine the overview column if name-specific
        overview = (row.get(f"overview_what_is_{slug.replace('-', '_')}") or "").strip()
        if not overview:
            # Fallback to search any column starting with overview_what_is
            for k, v in row.items():
                if (
                    k
                    and isinstance(k, str)
                    and k.startswith("overview_what_is_")
                    and v
                    and isinstance(v, str)
                    and v.strip()
                ):
                    overview = v.strip()
                    break

        fda_status = (row.get("fda_approval_status") or "").strip()
        wada_status = (row.get("wada_status") or "").strip()

        extra = self._extra_columns(row)
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
            "key_information": (row.get("overview_key_benefits") or "").strip(),
            **extra,
        }

    def extras(self, row: dict[str, Any]) -> dict[str, Any]:
        """Values the scraper reads that no peptides column can hold yet. Reported in the sync
        result, never written. ``research_stage`` is pep-pedia's maturity label (Well Researched,
        Limited Research, ...); peptides.research_level is the development-phase enum, so the two
        must not be mixed (AWD-16 adds a research_stage column)."""
        return {"research_stage": _clean(row.get("research_level")) or None}

    def _extra_columns(self, row: dict[str, Any]) -> dict[str, Any]:
        by_key = {_norm(k): v for k, v in row.items() if isinstance(k, str)}
        out: dict[str, Any] = {}
        for column, aliases in _SINGLE.items():
            out[column] = next((_clean(by_key[a]) for a in aliases if _clean(by_key.get(a))), "")
        half = next((_clean(by_key[a]) for a in _HALF_LIFE if _clean(by_key.get(a))), "")
        match = _HALF_LIFE_RE.search(half)
        out["half_life_value"] = float(match.group(1)) if match else None
        out["half_life_unit"] = _UNITS[match.group(2).lower()] if match else ""
        for column, prefixes in _MULTI.items():
            lines = [
                _clean(v)
                for k, v in by_key.items()
                if any(k == p or k.startswith(p + "_") for p in prefixes) and _clean(v)
            ]
            out[column] = "\n".join(lines)
        return out

    def _extract_contraindications(self, row: dict[str, Any]) -> str:
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

    def _extract_stop_signs(self, row: dict[str, Any]) -> str:
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
                    suffix = key[len(prefix) :].strip()
                    stop_items[suffix] = trimmed

        return json.dumps(stop_items) if stop_items else json.dumps([])
