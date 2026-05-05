import csv
import json
from src.mappers.peptide_mapper import PeptideMapper
from src.mappers.related_entity_mappers import (
    SideEffectMapper, 
    ProtocolMapper, 
    ReconstitutionMapper, 
    AdministrationMethodMapper,
    BenefitMapper,
    ResearchIndicationMapper,
    PeptideInteractionMapper,
    QualityIndicatorMapper,
    ReferenceMapper
)

def verify_mappers(csv_path: str):
    peptide_mapper = PeptideMapper()
    side_effect_mapper = SideEffectMapper()
    protocol_mapper = ProtocolMapper()
    reconstitution_mapper = ReconstitutionMapper()
    admin_method_mapper = AdministrationMethodMapper()
    benefit_mapper = BenefitMapper()
    research_indication_mapper = ResearchIndicationMapper()
    peptide_interaction_mapper = PeptideInteractionMapper()
    quality_indicator_mapper = QualityIndicatorMapper()
    reference_mapper = ReferenceMapper()
    
    results = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            p_data = peptide_mapper.map(row)
            if not p_data.get('name'):
                continue
                
            p_se = side_effect_mapper.map(row)
            p_proto = protocol_mapper.map(row)
            p_recon = reconstitution_mapper.map(row)
            p_admin = admin_method_mapper.map(row)
            p_ben = benefit_mapper.map(row)
            p_ind = research_indication_mapper.map(row)
            p_int = peptide_interaction_mapper.map(row)
            p_qual = quality_indicator_mapper.map(row)
            p_ref = reference_mapper.map(row)
            
            pep_name = p_data.get('name')
            if pep_name not in results:
                results[pep_name] = {
                    "peptide": p_data,
                    "administration_methods": [],
                    "side_effects": [],
                    "protocols": [],
                    "reconstitution_steps": [],
                    "benefits": [],
                    "research_indications": [],
                    "peptide_interactions": [],
                    "quality_indicators": [],
                    "references": []
                }
            
            # Simple aggregation (avoiding exact duplicates)
            for m in p_admin:
                if m not in results[pep_name]["administration_methods"]: results[pep_name]["administration_methods"].append(m)
            for m in p_se:
                if m not in results[pep_name]["side_effects"]: results[pep_name]["side_effects"].append(m)
            for m in p_proto:
                if m not in results[pep_name]["protocols"]: results[pep_name]["protocols"].append(m)
            for m in p_recon:
                if m not in results[pep_name]["reconstitution_steps"]: results[pep_name]["reconstitution_steps"].append(m)
            for m in p_ben:
                if m not in results[pep_name]["benefits"]: results[pep_name]["benefits"].append(m)
            for m in p_ind:
                if m not in results[pep_name]["research_indications"]: results[pep_name]["research_indications"].append(m)
            for m in p_int:
                if m not in results[pep_name]["peptide_interactions"]: results[pep_name]["peptide_interactions"].append(m)
            for m in p_qual:
                if m not in results[pep_name]["quality_indicators"]: results[pep_name]["quality_indicators"].append(m)
            for m in p_ref:
                if m not in results[pep_name]["references"]: results[pep_name]["references"].append(m)
            
    print(f"Processed {len(results)} unique peptides.")
    if results:
        first_key = list(results.keys())[0]
        print(f"\n--- Output for {first_key} ---")
        print(json.dumps(results[first_key], indent=2))
        
if __name__ == "__main__":
    verify_mappers("output_v6/pep_pedia_master.csv")
