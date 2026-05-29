import json
from src.mappers.db_import_orchestrator import DbImportOrchestrator

def test_mapping():
    orchestrator = DbImportOrchestrator()
    
    # Sample row reflecting the columns found in pep_pedia_master.csv
    sample_row = {
        "Peptide_Name": "BPC-157",
        "Full_Name": "Body Protection Compound 157",
        "Method": "Injectable, Oral",
        "overview_what_is_bpc_157": "BPC-157 is a pentadecapeptide...",
        "overview_mechanism_of_action": "It works by promoting angiogenesis...",
        "overview_key_benefits": "Wound healing. Joint health. Gut repair.",
        "side_effects_and_safety_side_effects_1": "Mild nausea",
        "side_effects_and_safety_side_effects_2": "Headache",
        "side_effects_and_safety_when_to_stop_1": "Severe abdominal pain",
        "typical_dose": "250-500 mcg",
        "route": "Injectable (SubQ: abdomen, thigh)",
        "research_protocols_goal_1": "Conservative starting",
        "research_protocols_dose_1": "250 mcg",
        "research_protocols_frequency_1": "1x daily",
        "research_protocols_route_1": "Injectable (SubQ)",
        "peptide_interactions_tb_500_synergistic": "Synergistic effect for tissue repair.",
        "research_indications_longevity_most_effective_(tissue_repair)": "Highly effective for tissue repair.",
        "references_research_studies_(Study_A)": "http://example.com/study_a",
        "what_to_expect_1": "Improved recovery in 1 week"
    }
    
    payload = orchestrator.map_row(sample_row)
    
    print("\n--- Group A (Lookups) ---")
    print(json.dumps(payload["group_a"], indent=2))
    
    print("\n--- Group B (Peptide) ---")
    print(json.dumps(payload["group_b"], indent=2))
    
    print("\n--- Relations (Groups C-F) ---")
    print(json.dumps(payload["relations"], indent=2))
    
    print("\n--- Protocols ---")
    print(json.dumps(payload["protocols"], indent=2))

if __name__ == "__main__":
    test_mapping()
