# Scraped CSV to JSON Payload Structure Mapping

This document maps the columns found in the scraped CSV (e.g., `output_v6/pep_pedia_master.csv`) to the hierarchical JSON payload structured defined in `mapper.md`. This payload matches the required dependencies and ordering for insertion into the database schema.

## 1. Top-Level Peptide Entity (`peptides`)

*   `Peptide_Name` -> `peptide.name`
*   `Full_Name` -> `peptide.synonyms`
*   `overview_what_is_[peptide]` (dynamic match) -> `peptide.overview`
*   `overview_mechanism_of_action` -> `peptide.mechanism_of_action`
*   `cycle` -> `peptide.cycle_duration`
*   `storage` -> `peptide.storage_temperature`
*   `molecular_information_amino_acid_sequence` -> `peptide.sequence` (if present)

## 2. Benefits (`benefits` & `peptide_benefits`)
*   `overview_key_benefits` -> Must be split by commas (or periods) into an array of individual strings/objects.
    *   **Mapping:** `peptide.benefits` -> `[ { "name": "Enhanced NAD+ levels" }, ... ]`

## 3. Side Effects (`side_effects` & `peptide_side_effects`)
*   `side_effects_and_safety_side_effects_X` (where X is 1 to 7+) -> Array of individual side effects.
    *   **Mapping:** `peptide.side_effects` -> `[ { "name": "Nausea" }, ... ]`
*   `side_effects_and_safety_when_to_stop_X` -> Merged into a text block or array for `peptide.stop_signs`.

## 4. Interactions (`peptide_interactions`)
Based on dynamic fields like: `peptide_interactions_[secondary_peptide]_[interaction_type]` (e.g., `peptide_interactions_nad+_precursors_(nmn,_nr)_synergistic`)
*   **Secondary Peptide Name**: Extracted from column name between `peptide_interactions_` and the last `_[type]`.
*   **Interaction Type**: The last suffix in the column name (e.g., `synergistic`, `compatible`).
*   **Description**: The cell's text value.
    *   **Mapping:** `peptide.interactions` -> `[ { "peptide_name_2": "NAD+ Precursors", "interaction_type": "synergistic", "description": "..." } ]`

## 5. Protocols (`peptide_protocols` umbrella)

Because a single row in the CSV usually represents a specific Peptide + Method combination, the base protocol attributes come directly from the row.
*   `Method` -> `protocol.administration_method` (e.g., "Injectable", "Oral")
*   `what_to_expect_X` -> Becomes a JSON array under `protocol.expectations` -> `[ "Week 1: Energy increase", ... ]`

### 5.1 Reconstitution Steps (`peptide_protocol_reconstitution_steps`)
*   `how_to_reconstitute_others` -> Parsed line-by-line or by numbered steps.
    *   **Mapping:** `protocol.reconstitution_steps` -> `[ { "step_number": 1, "description": "..." } ]`

### 5.2 Quality Indicators (`protocol_quality_indicators`)
Based on columns starting with `quality_indicators_`:
*   **Indicator Title**: The extracted end of the column name (e.g., `white_to_off-white_capsules` -> "White to off-white capsules").
*   **Description**: The cell's text value.
    *   **Mapping:** `protocol.quality_indicators` -> `[ { "indicator_title": "...", "indicator_description": "..." } ]`

### 5.3 Application Places (`application_places` & `protocol_application_places`)
*   `route` -> Provides context for places (e.g., "Injectable (SubQ: abdomen, thigh, arm)"). Parses into places.
    *   **Mapping:** `protocol.application_places` -> `[ "abdomen", "thigh", "arm" ]`

### 5.4 Dosages & Schedules (`dosages`, `schedules`, `protocol_dosages`)
Extracted from both generic and enumerated columns.

**Generic dosage:**
*   `typical_dose` -> Amount and Unit mappings.

**Enumerated research protocols (X = 1 to 5):**
*   `research_protocols_goal_X` -> Maps to `dosage.name` (e.g., "Conservative starting") or protocol sub-name.
*   `research_protocols_dose_X` -> Maps to `amount` and `unit`.
*   `research_protocols_frequency_X` -> Maps to `schedule.name` or `frequency`.
    *   **Mapping:**
        ```json
        "dosages": [
          {
            "name": "Conservative starting",
            "amount": "150-250",
            "unit": "mcg",
            "schedule": "1x daily"
          }
        ]
        ```

## 6. Research Indications (`peptide_research_indications`)
Based on dynamic columns like: `research_indications_[category]_[tag]_([specific_indication])`
*   **Category/Indication**: Embedded in the column name (e.g., *Longevity (NAD+ Enhancement)*).
*   **Tag**: Extracted enum value (e.g., `most_effective`, `moderate`).
*   **Description**: The cell value.
    *   **Mapping:** `peptide.research_indications` -> `[ { "indication_title": "NAD+ Enhancement", "effectiveness_tag": "most_effective", "description": "..." } ]`

## 7. Research Studies & Citations (`references`)
Based on columns like: `references_research_studies_([title])`
*   **Title**: Extracted from column name between parentheses.
*   **Value (URL/Abstract)**: The cell's text value.
    *   **Mapping:** `peptide.references` -> `[ { "reference_type": "study", "title": "Muscle Function...", "abstract": "..." } ]`

## 8. Pharmacokinetics/Graph Data
*   `graph_data_json` -> Direct pass-through to a JSONB column (e.g., `pharmacokinetics_json` inside the peptide record).

---

## Final Integrated JSON Structure Target

Based on the rules above and the `mapper.md` hierarchy, the parsing script should map a single CSV row into following object, which is ready to be sequentially inserted into the normalized DB:

```json
{
  "peptide": {
    "name": "CSV: Peptide_Name",
    "synonyms": "CSV: Full_Name",
    "overview": "CSV: overview_what_is_[peptide]",
    "mechanism_of_action": "CSV: overview_mechanism_of_action",
    "cycle_duration": "CSV: cycle",
    "storage_temperature": "CSV: storage",
    "sequence": "CSV: molecular_information_amino_acid_sequence",
    "stop_signs": "CSV[Array]: side_effects_and_safety_when_to_stop_X",
    "pharmacokinetics_json": "CSV: graph_data_json",
    
    "benefits": [
      { "name": "CSV: overview_key_benefits (parsed via comma/period delimiter)" }
    ],
    
    "side_effects": [
      { "name": "CSV: side_effects_and_safety_side_effects_X" }
    ],
    
    "interactions": [
      {
        "peptide_name_2": "CSV_ColName: Extracted secondary peptide",
        "interaction_type": "CSV_ColName: Extracted type enum",
        "description": "CSV_Cell: Row Value"
      }
    ],

    "research_indications": [
      {
        "indication_title": "CSV_ColName: Extracted indication",
        "effectiveness_tag": "CSV_ColName: Extracted tag enum",
        "description": "CSV_Cell: Row Value"
      }
    ],

    "references": [
      {
        "reference_type": "study",
        "title": "CSV_ColName: Extracted title",
        "abstract": "CSV_Cell: Row Value"
      }
    ],
    
    "protocols": [
      {
        "administration_method": "CSV: Method",
        "name": "Base Protocol",
        "expectations": "CSV[Array]: what_to_expect_X (converted to JSON array)",
        
        "application_places": [ "CSV: route (parsed by delimiter/tags)" ],
        
        "reconstitution_steps": [
          {
            "step_number": "Parsed number from row or auto-incremented",
            "description": "CSV: how_to_reconstitute_others (parsed line by line)"
          }
        ],
        
        "quality_indicators": [
          {
            "indicator_title": "CSV_ColName: Extracted title",
            "indicator_description": "CSV_Cell: Row Value"
          }
        ],

        "dosages": [
          {
            "name": "CSV: research_protocols_goal_X",
            "amount": "CSV: research_protocols_dose_X (Number part)",
            "unit": "CSV: research_protocols_dose_X (Unit part, e.g., mcg)",
            "schedule": "CSV: research_protocols_frequency_X"
          }
        ]
      }
    ]
  }
}
```
