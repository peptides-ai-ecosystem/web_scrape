import re
from typing import Any, Dict, List, Tuple
from src.mappers.base import BaseMapper


def parse_dosage_string(dose_str: str) -> Tuple[str, str]:
    """
    Parse a dosage string to extract amount and unit.
    Returns (amount, unit) as strings.
    On parse failure, returns ("", "") to avoid errors.
    
    Examples:
        "100 mcg" → ("100", "mcg")
        "0.5mg/ml" → ("0.5", "mg/ml")
        "2%" → ("2", "%")
        "150-250mcg" → ("150-250", "mcg")
        "~5mg/kg/day" → ("5", "mg/kg/day")
        "Invalid text" → ("", "")
    """
    if not dose_str or not isinstance(dose_str, str):
        return ("", "")
    
    dose_str = dose_str.strip()
    if not dose_str:
        return ("", "")
    
    try:
        # Remove leading special characters (~, ≈, etc.) but keep them in mind
        cleaned = dose_str.lstrip('~≈±')
        
        # Remove trailing parenthetical info like "(...)" for unit extraction
        # Keep amount as-is
        main_part = re.sub(r'\s*\(.*\)\s*$', '', cleaned).strip()
        
        # Pattern to match:
        # - optional number with optional decimal
        # - optional range with dash and another number
        # - optional spaces
        # - remaining text as unit
        match = re.match(r'^([0-9]*\.?[0-9]+(?:\s*-\s*[0-9]*\.?[0-9]+)?)\s*(.*)$', main_part)
        
        if match:
            amount = match.group(1).strip()
            unit = match.group(2).strip()
            return (amount, unit)
        else:
            # No numeric part found
            return ("", "")
    except Exception:
        # On any exception, return empty values
        return ("", "")

class AdministrationMethodMapper(BaseMapper):
    """Group A: Maps administration methods (e.g., Injectable, Oral)."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        methods = []
        method_str = (row.get("Method") or "").strip()
        if method_str:
            for m in [x.strip() for x in method_str.split(',') if x.strip()]:
                methods.append({
                    "name": m[:100],  # Truncate to 100 chars (administration_methods.name limit)
                    "description": f"{m} administration method"
                })
        return methods

class BenefitMapper(BaseMapper):
    """Group A: Maps general benefits."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        benefits = []
        key_benefits = (row.get("overview_key_benefits") or "").strip()
        if key_benefits:
            parts = re.split(r'[.]', key_benefits)
            for benefit in [b.strip() for b in parts if b.strip()]:
                benefits.append({
                    "name": benefit[:100],
                    "description": benefit
                })
        return benefits

class SideEffectMapper(BaseMapper):
    """Group A: Maps potential side effects."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        side_effects = []
        for i in range(1, 10):
            val = (row.get(f"side_effects_and_safety_side_effects_{i}") or "").strip()
            if val:
                parts = re.split(r'[.]', val)
                for side_effect in [s.strip() for s in parts if s.strip()]:
                    side_effects.append({
                        "name": side_effect[:100],  # Truncate to 100 chars (side_effects.name limit)
                        "description": side_effect
                    })
        return side_effects

class ScheduleMapper(BaseMapper):
    """Group A: Maps frequency and timing schedules."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        schedules = []
        for i in range(1, 6):
            freq = (row.get(f"research_protocols_frequency_{i}") or "").strip()
            if freq:
                schedules.append({
                    "name": freq[:100],  # Truncate to 100 chars (schedules.name limit)
                    "frequency": freq[:100]  # Truncate to 100 chars (schedules.frequency limit)
                })
        return schedules

class DosageMapper(BaseMapper):
    """Group A: Maps base dosage units and amounts."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        dosages = []
        typical = (row.get("typical_dose") or "").strip()
        if typical:
            amount, unit = parse_dosage_string(typical)
            dosages.append({"amount": amount, "unit": unit})
        
        for i in range(1, 6):
            dose = (row.get(f"research_protocols_dose_{i}") or "").strip()
            if dose:
                amount, unit = parse_dosage_string(dose)
                dosages.append({"amount": amount, "unit": unit})
                

        return dosages


class ResearchStudyMapper(BaseMapper):
    """Group A: Maps external research studies and citations."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        studies = []
        for key, val in row.items():
            if val:
                if key and isinstance(key, str) and key.startswith("references_research_studies_"):
                    title_match = re.search(r"references_research_studies_\((.*)\)", key)
                    title = title_match.group(1).replace('_', ' ') if title_match else val[:50]
                    studies.append({
                        "title": title,
                        "url": val if val.startswith("http") else "",
                        "abstract": val if not val.startswith("http") else "",
                        "type": "study"
                    })
                elif key and isinstance(key, str) and key.startswith("references_citations_"):
                    # remove 'View Publication\n(opens in new tab)\nâ (opens in new tab)' variants
                    clean_val = re.sub(r'View Publication.*', '', val, flags=re.DOTALL).strip()
                    full_abstract = clean_val # Keep full cleaned text for abstract
                    
                    # Extract DOI
                    doi_match = re.search(r'DOI:\s*(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', clean_val, re.IGNORECASE)
                    doi = doi_match.group(1) if doi_match else ""
                    if doi_match:
                        clean_val = (clean_val[:doi_match.start()] + " " + clean_val[doi_match.end():]).strip()
                        
                    # Extract Authors and Title
                    author_match = re.search(r'^(.*?)\(\d{4}\)\.', clean_val)
                    if author_match:
                        authors = author_match.group(1).strip()
                        title = clean_val[author_match.end():].strip()
                    else:
                        authors = ""
                        title = clean_val
                        
                    studies.append({
                        "title": title if title else "Citation",
                        "authors": authors,
                        "doi": doi,
                        "url": val if val.startswith("http") else "",
                        "abstract": full_abstract,
                        "type": "citation"
                    })
        return studies
