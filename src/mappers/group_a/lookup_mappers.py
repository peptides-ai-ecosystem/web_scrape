import re
from typing import Any, Dict, List
from src.mappers.base import BaseMapper

class AdministrationMethodMapper(BaseMapper):
    """Group A: Maps administration methods (e.g., Injectable, Oral)."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        methods = []
        method_str = row.get("Method", "").strip()
        if method_str:
            for m in [x.strip() for x in method_str.split(',') if x.strip()]:
                methods.append({
                    "name": m,
                    "description": f"{m} administration method"
                })
        return methods

class BenefitMapper(BaseMapper):
    """Group A: Maps general benefits."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        benefits = []
        key_benefits = row.get("overview_key_benefits", "").strip()
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
            val = row.get(f"side_effects_and_safety_side_effects_{i}", "").strip()
            if val:
                parts = re.split(r'[.]', val)
                for side_effect in [s.strip() for s in parts if s.strip()]:
                    side_effects.append({
                        "name": side_effect[:100],
                        "description": side_effect
                    })
        return side_effects

class ScheduleMapper(BaseMapper):
    """Group A: Maps frequency and timing schedules."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        schedules = []
        for i in range(1, 6):
            freq = row.get(f"research_protocols_frequency_{i}", "").strip()
            if freq:
                schedules.append({"name": freq, "frequency": freq})
        return schedules

class DosageMapper(BaseMapper):
    """Group A: Maps base dosage units and amounts."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        dosages = []
        typical = row.get("typical_dose", "").strip()
        if typical:
            dosages.append({"amount": typical, "unit": ""})
        
        for i in range(1, 6):
            dose = row.get(f"research_protocols_dose_{i}", "").strip()
            if dose:
                dosages.append({"amount": dose, "unit": ""})
        return dosages


class ResearchStudyMapper(BaseMapper):
    """Group A: Maps external research studies and citations."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        studies = []
        for key, val in row.items():
            if val:
                if key.startswith("references_research_studies_"):
                    title_match = re.search(r"references_research_studies_\((.*)\)", key)
                    title = title_match.group(1).replace('_', ' ') if title_match else val[:50]
                    studies.append({
                        "title": title,
                        "url": val if val.startswith("http") else "",
                        "abstract": val if not val.startswith("http") else "",
                        "type": "study"
                    })
                elif key.startswith("references_citations_"):
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
