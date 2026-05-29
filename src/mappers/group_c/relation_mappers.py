import re
from typing import Any, Dict, List
from src.mappers.base import BaseMapper
from src.mappers.group_a.lookup_mappers import BenefitMapper, SideEffectMapper, ResearchStudyMapper

class RelationMapper(BaseMapper):
    """
    Group C: Maps peptide-specific relations.
    """
    
    def __init__(self):
        # Instantiate Group A mappers to reuse their parsing logic
        self.benefit_mapper = BenefitMapper()
        self.side_effect_mapper = SideEffectMapper()
        self.study_mapper = ResearchStudyMapper()
    
    def map(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "benefits": self._map_benefits(row),
            "side_effects": self._map_side_effects(row),
            "interactions": self._map_interactions(row),
            "indications": self._map_indications(row),
            "references": self._map_references(row)
        }

    def _map_benefits(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Use Group A mapper to ensure identical processing
        benefits = self.benefit_mapper.map(row)
        return [{"benefit_name": b["name"]} for b in benefits]

    def _map_side_effects(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Use Group A mapper to ensure identical processing
        side_effects = self.side_effect_mapper.map(row)
        return [{"side_effect_name": se["name"]} for se in side_effects]

    def _map_interactions(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        interactions = []
        for key, val in row.items():
            if val and key and isinstance(key, str) and key.startswith("peptide_interactions_"):
                parts = key.replace("peptide_interactions_", "").split("_")
                if len(parts) >= 2:
                    interaction_type = parts[-1]
                    name_raw = "_".join(parts[:-1]).replace("-", " ")
                    secondary_peptide = name_raw.replace("_", " ").title()
                    interactions.append({
                        "secondary_peptide_name": secondary_peptide,
                        "interaction_type": interaction_type,
                        "description": val
                    })
        return interactions

    def _map_indications(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        indications = []
        for key, val in row.items():
            if val and key and isinstance(key, str) and key.startswith("research_indications_"):
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
                    "effectiveness_tag": tag,
                    "description": val
                })
        return indications

    def _map_references(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Use Group A mapper to ensure identical processing
        return self.study_mapper.map(row)
