from typing import Any, Dict, List
from src.mappers.base_mapper import BaseMapper
import re


class SideEffectMapper(BaseMapper):
    """Maps side constraints to side_effects and linkage table configurations."""

    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        side_effects = []
        for i in range(1, 10):
            val = row.get(f"side_effects_and_safety_side_effects_{i}", "").strip()
            if val:
                side_effects.append({
                    "name": val[:100],  # Shortened to fit typical name varchar(100)
                    "description": val,
                    "severity_level": "", # Default, can be refined based on keywords
                    "frequency": ""
                })
        return side_effects


class ProtocolMapper(BaseMapper):
    """Parses and maps research protocols and expectations."""

    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        protocols = []
        
        # Parse expectations
        expectations = []
        for i in range(1, 6):
            exp = row.get(f"what_to_expect_{i}", "").strip()
            if exp:
                expectations.append(exp)
                
        # Look for protocols 1 through 5
        for i in range(1, 6):
            goal = row.get(f"research_protocols_goal_{i}", "").strip()
            if goal:
                dose = row.get(f"research_protocols_dose_{i}", "").strip()
                frequency = row.get(f"research_protocols_frequency_{i}", "").strip()
                route = row.get(f"research_protocols_route_{i}", "").strip()
                
                protocol_data = {
                    "name": goal,
                    "description": f"Goal: {goal}. Route: {route}",
                    "route_name": route,
                    "dose_text": dose,
                    "frequency_text": frequency,
                    "expectations": expectations
                }
                protocols.append(protocol_data)

        # Baseline protocol if only typical_dose and route are found, without specific research protocols
        # or just add it alongside
        typical_dose = row.get("typical_dose", "").strip()
        main_route = row.get("route", "").strip()
        method = row.get("Method", "").strip()
        
        if typical_dose or main_route:
            # We can create a baseline protocol or inject generic info
            baseline_name = method if method else "Typical Protocol"
            
            # Prevent duplicate basically identical protocol
            if not any(p["name"] == baseline_name and p["dose_text"] == typical_dose for p in protocols):
                protocols.append({
                    "name": baseline_name,
                    "description": f"Typical Protocol. Main Route: {main_route}",
                    "route_name": main_route,
                    "dose_text": typical_dose,
                    "frequency_text": "",
                    "expectations": expectations
                })

        return protocols


class ReconstitutionMapper(BaseMapper):
    """Parses reconstruction steps."""
    
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps = []
        for i in range(1, 10):
            # Sometimes steps are split across numbered columns, sometimes single text
            val = row.get(f"how_to_reconstitute_others_{i}", "").strip() or row.get(str(i), "").strip()
            if val and len(val) > 2:
                steps.append({
                    "step_number": i,
                    "description": val
                })
        return steps


class AdministrationMethodMapper(BaseMapper):
    """Parses and maps administration methods."""

    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        methods = []
        method = row.get("Method", "").strip()
        if method:
            # E.g. "Injectable, Oral" could technically be split, but for now we take it
            # and split by commas if there are multiple, or just take as is.
            # Assuming simple comma separation might exist:
            for m in [x.strip() for x in method.split(',') if x.strip()]:
                methods.append({
                    "name": m,
                    "description": f"{m} administration method"
                })
        return methods

class BenefitMapper(BaseMapper):
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        benefits = []
        key_benefits = row.get("overview_key_benefits", "").strip()
        if key_benefits:
            for benefit in [b.strip() for b in key_benefits.split('.') if b.strip()]:
                benefits.append({
                    "name": benefit[:100],
                    "description": benefit
                })
        return benefits
        
class ResearchIndicationMapper(BaseMapper):
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        indications = []
        for key, val in row.items():
            if val and key.startswith("research_indications_"):
                match = re.search(r"research_indications_(.+?)_(most_effective|effective|moderate)_?\((.*)\)?", key)
                if match:
                    category = match.group(1).replace('_', ' ').title()
                    tag = match.group(2)
                    specific = match.group(3).strip("()_").replace('_', ' ').title()
                    name = f"{category} ({specific})" if specific else category
                else:
                    name = key.replace('research_indications_', '').replace('_', ' ').title()
                    tag = "effective"
                indications.append({
                    "indication_title": name,
                    "effectiveness_tag": tag
                })
        return indications

class PeptideInteractionMapper(BaseMapper):
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        interactions = []
        for key, val in row.items():
            if val and key.startswith("peptide_interactions_"):
                parts = key.replace("peptide_interactions_", "").split("_")
                if len(parts) >= 2:
                    interaction_type = parts[-1]
                    secondary_peptide = "_".join(parts[:-1]).replace("-", " ").title()
                    interactions.append({
                        "secondary_peptide_name": secondary_peptide,
                        "interaction_type": interaction_type,
                        "description": val
                    })
        return interactions

class QualityIndicatorMapper(BaseMapper):
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        indicators = []
        for key, val in row.items():
            if val and key.startswith("quality_indicators_"):
                title = key.replace("quality_indicators_", "").replace("_", " ").title()
                indicators.append({
                    "indicator_title": title,
                    "indicator_description": val
                })
        return indicators

class ReferenceMapper(BaseMapper):
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        references = []
        for key, val in row.items():
            if val and key.startswith("references_research_studies_"):
                title_match = re.search(r"references_research_studies_\((.*)\)", key)
                title = title_match.group(1).replace('_', ' ') if title_match else val[:50]
                references.append({
                    "reference_type": "study",
                    "title": title,
                    "url": val if val.startswith("http") else "",
                    "abstract": val if not val.startswith("http") else ""
                })
            elif val and key.startswith("references_citations_"):
                references.append({
                    "reference_type": "citation",
                    "title": f"Citation",
                    "url": val if val.startswith("http") else "",
                    "abstract": val if not val.startswith("http") else ""
                })
        return references
