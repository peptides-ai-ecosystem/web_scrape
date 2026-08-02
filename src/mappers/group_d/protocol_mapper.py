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
        
        # Base expectations: what_to_expect_{1..n} columns contain "<period>: <statement>".
        # Build a key:value object keyed by the period, preserving CSV order —
        # the same shape as peptides.contraindications (see PeptideMapper).
        expectations = self._extract_expectations(row)
        
        method = (row.get("Method") or "").strip()
        main_route = (row.get("route") or "").strip()
        
        # Quick start guide as a key:value JSON object:
        #   typical_dose        ← quick_guide_typical_dose
        #   mechanism_of_action ← overview_mechanism_of_action (overview section)
        #   key_benefits        ← overview_key_benefits (overview section)
        #   effects_timeline    ← quick_guide_effects_timeline
        #   best_timing         ← quick_guide_best_timing
        quick_start_json = self._extract_quick_start_guide(row)
        
        key_benefits = (row.get("overview_key_benefits") or row.get("key_benefits", "")).strip()
        moa = (row.get("overview_mechanism_of_action") or row.get("mechanism_of_action", "")).strip()
        timing = (row.get("quick_guide_best_timing") or row.get("best_timing") or "").strip()
        effects = (row.get("quick_guide_effects_timeline") or row.get("effects_timeline") or "").strip()

        # Find dynamic description (overview_what_is_<peptide>)
        description = ""
        for k, v in row.items():
            if k and isinstance(k, str) and k.startswith("overview_what_is_") and v and isinstance(v, str) and v.strip():
                description = v.strip()
                break

        # Extract research protocols
        for i in range(1, 6):
            goal = (row.get(f"research_protocols_goal_{i}") or "").strip()
            if goal:
                dose = (row.get(f"research_protocols_dose_{i}") or "").strip()
                freq = (row.get(f"research_protocols_frequency_{i}") or "").strip()
                route = (row.get(f"research_protocols_route_{i}") or "").strip() or main_route
                
                protocols.append({
                    "name": goal[:100],
                    "description": description,
                    "administration_method_name": method,
                    "route_name": route,
                    "expectations": expectations,
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
                "expectations": expectations,
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

    def _extract_expectations(self, row: Dict[str, Any]) -> str:
        """Extract what_to_expect_{1..n} columns as a key:value JSON object.

        CSV values look like "Week 1-2: Reduced inflammation..." so the text
        before the first colon becomes the key and the statement the value —
        the same shape as peptides.contraindications. Values without a colon
        fall back to a "Note N" key.
        """
        expectations = {}
        for i in range(1, 6):
            value = (row.get(f"what_to_expect_{i}") or "").strip()
            if not value:
                continue
            if ":" in value:
                key, _, statement = value.partition(":")
                key = key.strip()
                statement = statement.strip()
            else:
                key, statement = f"Note {len(expectations) + 1}", value.strip()
            if key and statement:
                expectations[key] = statement
        return json.dumps(expectations) if expectations else json.dumps([])

    def _extract_quick_start_guide(self, row: Dict[str, Any]) -> str:
        """Build the quick_start_guide JSON object from the quick guide CSV columns.

        Every CSV column starting with ``quick_guide_`` (e.g. quick_guide_typical_dose)
        becomes a key:value entry keyed by the column name minus the prefix
        (e.g. {"typical_dose": "250-500 mcg"}). mechanism_of_action and
        key_benefits are added from the overview section columns.
        """
        guide = {}
        for key, value in row.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            prefix = None
            if key.startswith("quick_start_guide_"):
                prefix = "quick_start_guide_"
            elif key.startswith("quick_guide_"):
                prefix = "quick_guide_"
            if prefix:
                trimmed = value.strip()
                if trimmed:
                    guide[key[len(prefix):]] = trimmed

        for field, col in (
            ("mechanism_of_action", "overview_mechanism_of_action"),
            ("key_benefits", "overview_key_benefits"),
        ):
            value = row.get(col)
            if value and isinstance(value, str) and value.strip():
                guide[field] = value.strip()

        return json.dumps(guide) if guide else json.dumps([])
