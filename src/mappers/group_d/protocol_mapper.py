import json
from typing import Any, Dict, List
from src.mappers.base import BaseMapper
from src.mappers.group_e.detail_mappers import (
    ReconstitutionMapper,
    QualityMapper,
    ApplicationPlaceMapper,
    ProtocolDosageMapper
)

class ProtocolMapper(BaseMapper):
    """Group D: Maps protocols and coordinates Group E details."""
    
    def __init__(self):
        self.reconst_mapper = ReconstitutionMapper()
        self.quality_mapper = QualityMapper()
        self.place_mapper = ApplicationPlaceMapper()
        self.dosage_mapper = ProtocolDosageMapper()

    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        protocols = []
        
        # Base expectations (Formatted as JSON here, logic moved from db_manager)
        expectations = [row.get(f"what_to_expect_{i}", "").strip() for i in range(1, 6) if row.get(f"what_to_expect_{i}", "").strip()]
        expectations_json = json.dumps(expectations)
        
        method = row.get("Method", "").strip()
        main_route = row.get("route", "").strip()
        
        # Extraction of new fields
        # Try multiple potential keys for quick_start_guide
        quick_start = (
            row.get("how_to_take_others") or 
            row.get("how_to_reconstitute_others") or 
            row.get("quick_start_guide", "")
        ).strip()
        quick_start_list = [item.strip() for item in quick_start.split("\n") if item.strip()]
        quick_start_json = json.dumps(quick_start_list) if quick_start_list else json.dumps([])
        
        key_benefits = (row.get("overview_key_benefits") or row.get("key_benefits", "")).strip()
        moa = (row.get("overview_mechanism_of_action") or row.get("mechanism_of_action", "")).strip()
        timing = row.get("best_timing", "").strip()
        effects = row.get("effects_timeline", "").strip()

        # Find dynamic description (overview_what_is_<peptide>)
        description = ""
        for k, v in row.items():
            if k and isinstance(k, str) and k.startswith("overview_what_is_") and v and isinstance(v, str) and v.strip():
                description = v.strip()
                break

        # Extract research protocols
        for i in range(1, 6):
            goal = row.get(f"research_protocols_goal_{i}", "").strip()
            if goal:
                dose = row.get(f"research_protocols_dose_{i}", "").strip()
                freq = row.get(f"research_protocols_frequency_{i}", "").strip()
                route = row.get(f"research_protocols_route_{i}", "").strip() or main_route
                
                protocols.append({
                    "name": goal[:100],
                    "description": description,
                    "administration_method_name": method,
                    "route_name": route,
                    "expectations": expectations_json,
                    "quick_start_guide": quick_start_json,
                    "key_benefits": key_benefits,
                    "mechanism_of_action": moa,
                    "best_timing": timing,
                    "effects_timeline": effects,
                    "reconstitution_steps": self.reconst_mapper.map(row),
                    "quality_indicators": self.quality_mapper.map(row),
                    "application_places": self.place_mapper.map(row, route),
                    "dosages": self.dosage_mapper.map(row, goal, dose, freq, (i == 1))
                })
        
        # Default baseline
        if not protocols and (row.get("typical_dose") or main_route):
            protocols.append({
                "name": (method or "Default Protocol")[:100],
                "description": description,
                "administration_method_name": method,
                "route_name": main_route,
                "expectations": expectations_json,
                "quick_start_guide": quick_start_json,
                "key_benefits": key_benefits,
                "mechanism_of_action": moa,
                "best_timing": timing,
                "effects_timeline": effects,
                "reconstitution_steps": self.reconst_mapper.map(row),
                "quality_indicators": self.quality_mapper.map(row),
                "application_places": self.place_mapper.map(row, main_route),
                "dosages": self.dosage_mapper.map(row)
            })
            
        return protocols
