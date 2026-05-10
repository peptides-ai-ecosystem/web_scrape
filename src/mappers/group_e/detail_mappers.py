import re
from typing import Any, Dict, List
from src.mappers.base import BaseMapper

class ReconstitutionMapper(BaseMapper):
    """Group E: Maps protocol reconstitution steps."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps = []
        for i in range(1, 10):
            val = row.get(f"research_protocols_reconstitution_step_{i}", "").strip()
            if val:
                steps.append({"step_number": i, "description": val})
        return steps

class QualityMapper(BaseMapper):
    """Group E: Maps protocol quality indicators."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        indicators = []
        for i in range(1, 10):
            val = row.get(f"research_protocols_quality_indicator_{i}", "").strip()
            if val:
                indicators.append({
                    "indicator_title": f"Indicator {i}",
                    "indicator_description": val
                })
        return indicators

class ApplicationPlaceMapper(BaseMapper):
    """Group E: Maps protocol application places."""
    def map(self, row: Dict[str, Any], route: str = "") -> List[str]:
        places = []
        if not route:
            route = row.get("route", "").strip() or row.get("research_protocols_route_1", "").strip()
            
        if "(" in route and ")" in route:
            match = re.search(r"\((.*?)\)", route)
            if match:
                parts = match.group(1).split(":")
                place_list = parts[-1].split(",")
                places = [x.strip() for x in place_list if x.strip()]
        return places

class ProtocolDosageMapper(BaseMapper):
    """Group E: Maps dosages for specific protocols."""
    def map(self, row: Dict[str, Any], goal: str = "", dose: str = "", freq: str = "", is_default: bool = False) -> List[Dict[str, Any]]:
        payloads = []
        
        if dose:
            payloads.append({
                "amount": dose,
                "frequency": freq,
                "is_default": is_default,
                "notes": f"Amount: {dose}, Freq: {freq}" # Logic moved from db_manager
            })
        elif row.get("typical_dose"):
            typical_dose = row.get("typical_dose", "").strip()
            payloads.append({
                "amount": typical_dose,
                "is_default": True,
                "notes": f"Amount: {typical_dose}"
            })
            
        return payloads
