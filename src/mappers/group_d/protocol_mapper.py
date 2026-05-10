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
        
        # Extract research protocols
        for i in range(1, 6):
            goal = row.get(f"research_protocols_goal_{i}", "").strip()
            if goal:
                dose = row.get(f"research_protocols_dose_{i}", "").strip()
                freq = row.get(f"research_protocols_frequency_{i}", "").strip()
                route = row.get(f"research_protocols_route_{i}", "").strip() or main_route
                
                protocols.append({
                    "name": goal,
                    "administration_method_name": method,
                    "route_name": route,
                    "expectations": expectations_json, # Already JSON formatted
                    "reconstitution_steps": self.reconst_mapper.map(row),
                    "quality_indicators": self.quality_mapper.map(row),
                    "application_places": self.place_mapper.map(row, route),
                    "dosages": self.dosage_mapper.map(row, goal, dose, freq, (i == 1))
                })
        
        # Default baseline
        if not protocols and (row.get("typical_dose") or main_route):
            protocols.append({
                "name": method or "Default Protocol",
                "administration_method_name": method,
                "route_name": main_route,
                "expectations": expectations_json,
                "reconstitution_steps": self.reconst_mapper.map(row),
                "quality_indicators": self.quality_mapper.map(row),
                "application_places": self.place_mapper.map(row, main_route),
                "dosages": self.dosage_mapper.map(row)
            })
            
        return protocols
