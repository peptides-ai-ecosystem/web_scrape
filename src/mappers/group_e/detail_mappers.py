import re
import logging
from typing import Any, Dict, List
from src.mappers.base import BaseMapper

logger = logging.getLogger(__name__)

class ReconstitutionMapper(BaseMapper):
    """Group E: Maps protocol reconstitution steps."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps = []
        raw_text = row.get("how_to_reconstitute_others", "").strip()
        if not raw_text:
            return []
        
        # Split by newline and look for numeric step markers
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        
        current_step_num = None
        current_step_desc = []
        
        for line in lines:
            # Check if line is just a number (e.g. "1", "2")
            if line.isdigit():
                # Save previous step if exists
                if current_step_num is not None and current_step_desc:
                    steps.append({
                        "step_number": int(current_step_num),
                        "description": " ".join(current_step_desc)
                    })
                current_step_num = line
                current_step_desc = []
            elif current_step_num is not None:
                current_step_desc.append(line)
        
        # Save last step
        if current_step_num is not None and current_step_desc:
            steps.append({
                "step_number": int(current_step_num),
                "description": " ".join(current_step_desc)
            })
            
        if steps:
            logger.info(f"  [MAP_RECONSTITUTION] Extracted {len(steps)} steps from 'how_to_reconstitute_others'")
        return steps

class QualityMapper(BaseMapper):
    """Group E: Maps protocol quality indicators."""
    def map(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        indicators = []
        
        # Extract from columns starting with 'quality_indicators_'
        for key, val in row.items():
            if key and isinstance(key, str) and key.startswith("quality_indicators_") and val and isinstance(val, str) and val.strip():
                # Humanize the title from the key
                # e.g. quality_indicators_sterile_lyophilized_powder -> Sterile lyophilized powder
                title = key.replace("quality_indicators_", "").replace("_", " ").capitalize()
                
                indicators.append({
                    "indicator_title": title,
                    "indicator_description": val.strip()
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
