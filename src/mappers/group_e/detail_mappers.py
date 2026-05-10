import re
import logging
from typing import Any, Dict, List
from src.mappers.base import BaseMapper

logger = logging.getLogger(__name__)

class ReconstitutionMapper(BaseMapper):
    """Group E: Maps protocol reconstitution steps."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps = []
        for i in range(1, 10):
            val = row.get(f"research_protocols_reconstitution_step_{i}", "").strip()
            if val:
                steps.append({"step_number": i, "description": val})
        if steps:
            logger.info(f"  [MAP_RECONSTITUTION] Extracted {len(steps)} steps")
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
        if indicators:
            logger.info(f"  [MAP_QUALITY] Extracted {len(indicators)} indicators")
        return indicators

class ApplicationPlaceMapper(BaseMapper):
    """Group E: Maps protocol application places."""
    def map(self, row: Dict[str, Any], route: str = "") -> List[str]:
        # places = []
        if not route:
            route = row.get("route", "").strip() or row.get("research_protocols_route_1", "").strip()
        logger.info(f"  [MAP_APP_PLACE] Extracted route: {route}")
        
        return [route]

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
            
        if payloads:
            logger.info(f"  [MAP_DOSAGE] Extracted {len(payloads)} dosages for goal '{goal}'")
        return payloads
