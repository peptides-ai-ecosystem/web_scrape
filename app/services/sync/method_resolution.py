"""Scraped administration-method text -> the platform's canonical method name.

pep-pedia writes the Method as free text ("Nasal, Injectable"); the platform's
``administration_methods`` table holds the canonical names. One shared map so the
core sync and the evaluation builder cannot drift apart. An unresolved Method is
a reason to report, not a reason to drop the whole peptide (AID-4): the caller
still writes the peptide columns and every child that needs no method.
"""

from collections.abc import Collection
from typing import NamedTuple

# Order matters: the first keyword found in a part wins.
METHOD_KEYWORD_MAP: dict[str, str] = {
    "nasal": "Nasal Spray",
    "intranasal": "Nasal Spray",
    "spray": "Nasal Spray",
    "topical": "Topical Cream",
    "cream": "Topical Cream",
    "transdermal": "Topical Cream",
    "oral": "Capsule",
    "capsule": "Capsule",
    "tablet": "Capsule",
    "injectable": "Injectable",
    "injection": "Injectable",
    "subcutaneous": "Injectable",
    "subq": "Injectable",
    "intramuscular": "Injectable",
}


class MethodResolution(NamedTuple):
    method: str | None
    reason: str | None  # why nothing resolved; None when a method did


def resolve_method(raw_method: str | None, existing_names: Collection[str]) -> MethodResolution:
    """The first comma-separated part that maps to a method the DB has."""
    raw = str(raw_method or "").strip()
    if not raw:
        return MethodResolution(None, "no Method on the page")
    first_reason: str | None = None
    for part in (p.strip() for p in raw.split(",")):
        lowered = part.lower()
        mapped = next((name for keyword, name in METHOD_KEYWORD_MAP.items() if keyword in lowered), None)
        if mapped and mapped in existing_names:
            return MethodResolution(mapped, None)
        if first_reason is None:
            first_reason = f"mapped method '{mapped}' not in DB" if mapped else f"admin method '{part}' has no mapping"
    return MethodResolution(None, first_reason or f"admin method '{raw}' has no mapping")
