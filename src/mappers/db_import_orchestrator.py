import json
from typing import Any, Dict, List
from src.mappers.base_mapper import BaseMapper
from src.mappers.peptide_mapper import PeptideMapper
from src.mappers.related_entity_mappers import (
    ProtocolMapper, 
    SideEffectMapper, 
    ReconstitutionMapper,
    AdministrationMethodMapper,
    BenefitMapper,
    ResearchIndicationMapper,
    PeptideInteractionMapper,
    QualityIndicatorMapper,
    ReferenceMapper
)

class DbImportOrchestrator:
    """
    Orchestrates the conversion of a raw data row into a fully structured dictionary.
    """

    def __init__(self):
        self.peptide_mapper = PeptideMapper()
        self.protocol_mapper = ProtocolMapper()
        self.side_effect_mapper = SideEffectMapper()
        self.reconstitution_mapper = ReconstitutionMapper()
        self.admin_method_mapper = AdministrationMethodMapper()
        self.benefit_mapper = BenefitMapper()
        self.research_indication_mapper = ResearchIndicationMapper()
        self.peptide_interaction_mapper = PeptideInteractionMapper()
        self.quality_indicator_mapper = QualityIndicatorMapper()
        self.reference_mapper = ReferenceMapper()

    def map_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps a single CSV/scraped row into a multi-table insertion payload.
        """
        peptides_payload = self.peptide_mapper.map(row)
        
        # Build relational payload structure
        payload = {
            "peptides": peptides_payload,
            "related_inserts": {
                "protocols": self.protocol_mapper.map(row),
                "side_effects": self.side_effect_mapper.map(row),
                "reconstitution_steps": self.reconstitution_mapper.map(row),
                "administration_methods": self.admin_method_mapper.map(row),
                "benefits": self.benefit_mapper.map(row),
                "research_indications": self.research_indication_mapper.map(row),
                "peptide_interactions": self.peptide_interaction_mapper.map(row),
                "quality_indicators": self.quality_indicator_mapper.map(row),
                "references": self.reference_mapper.map(row)
            }
        }
        return payload

    def map_dataset(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Maps an entire dataset. Useful if passing output from scraper_manager.
        """
        return [self.map_row(row) for row in rows]

# Example usage to be imported anywhere:
# orchestrator = DbImportOrchestrator()
# supabase_payload = orchestrator.map_row(scraped_dict)
# response = supabase.table('peptides').insert(supabase_payload['peptides']).execute()
