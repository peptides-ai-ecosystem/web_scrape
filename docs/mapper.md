# Database Entity Relations Mapping

This document outlines the relational structure of the database based on the DBML schema, demonstrating how the raw scraped data should be normalized and mapped into the relational database.

## Core Entities
1. **Peptides** (`peptides`)
   - The central entity in the schema.
   - Primary Key: `id`

2. **Administration Methods** (`administration_methods`) 
   - Stores distinct methods (e.g., Injectable, Oral, Topical).
   - Primary Key: `id`
   - Relates to Peptides via Protocols.

## Relational Linkages & Hierarchy

### 1. Peptide Level Relations
- **Benefits**: `peptide_benefits` links directly to `benefits`.
- **Side Effects**: `peptide_side_effects` links directly to `side_effects`.
- **Interactions**: `peptide_interactions` links to other peptides (by ID or name).
- **Research Indications**: `peptide_research_indications` identifies use cases.
- **References**: `peptide_references` links to `research_studies` or `citations`.

### 2. Protocol Hierarchy (`peptide_protocols`)
The protocol is a specific use-case for a peptide via an administration method.
- **Core**: `peptides` + `administration_methods` -> `peptide_protocols`.
- **Protocol Children ("Protocols Others")**:
    - **Reconstitution**: `peptide_protocol_reconstitution_steps` (Step-by-step mixing).
    - **Quality**: `protocol_quality_indicators` (Verify product integrity).
    - **Application**: `protocol_application_places` (Junction to `application_places`).
    - **Research Context**: `peptide_research_indication_studies` (Links a specific indication to this protocol and a study).

### 3. Dosage & Benefit Hierarchy
- **Dosages**: `protocol_dosages` (Specific dose instances for a protocol).
    - **Dosage Benefits**: `protocol_dosage_benefits` (Benefits achieved *at this specific dose*).
    - **Dosage Side Effects**: `protocol_dosage_side_effects` (Side effects likely *at this specific dose*).

---

## Processing Flow Recommendation for Scraped Data

When transforming the flattened scraped data into structured insertion payloads, it is recommended to group the output relationally to guarantee integrity constraints (Foreign Keys).

```json
{
  "peptide": {
    "name": "BPC-157",
    "sequence": "...",
    "interactions": [
      { "peptide_name_2": "TB-500", "interaction_type": "synergistic", "description": "..." }
    ],
    "side_effects": [ "Nausea" ],
    "benefits": [ "Wound healing" ],
    "protocols": [
      {
        "administration_method": "Injectable",
        "name": "Healing Protocol",
        "reconstitution_steps": [ { "step_number": 1, "description": "..." } ],
        "quality_indicators": [ { "indicator_title": "...", "indicator_description": "..." } ],
        "application_places": [ "Belly fat" ],
        "dosages": [
          {
            "amount": 250,
            "unit": "mcg",
            "schedule": "Twice daily",
            "side_effects": [ { "name": "Redness at site", "likelihood": "common" } ],
            "benefits": [ { "name": "Faster recovery", "onset_time": "3 weeks" } ]
          }
        ]
      }
    ]
  }
}
```

### Dependency Insertion Order
To maintain referential integrity, inserts must follow this hierarchy (detailed in [structured.md](structured.md)):
1.  **Lookups**: `categories`, `administration_methods`, `benefits`, `side_effects`, `dosages`, `schedules`, `application_places`, `research_studies`.
2.  **Core**: `peptides`.
3.  **Peptide Bridges**: `peptide_benefits`, `peptide_side_effects`, `peptide_interactions`, `peptide_research_indications`, `peptide_references`.
4.  **Protocols**: `peptide_protocols`.
5.  **Protocol Details**: `peptide_protocol_reconstitution_steps`, `protocol_application_places`, `protocol_quality_indicators`, `protocol_dosages`.
6.  **Dosage/Study Context**: `protocol_dosage_benefits`, `protocol_dosage_side_effects`, `peptide_research_indication_studies`.

---

## Scraped CSV to JSON payload mapping

This document maps the columns found in the scraped CSV (e.g., `output_v6/pep_pedia_master.csv`) to the hierarchical JSON payload structure defined above. This payload matches the required dependencies and ordering for insertion into the database schema.

### 1. Top-Level Peptide Entity (`peptides`)

*   `Peptide_Name` -> `peptide.name`
*   `Full_Name` -> `peptide.synonyms`
*   `overview_what_is_[peptide]` (dynamic match) -> `peptide.overview`
*   `overview_mechanism_of_action` -> `peptide.mechanism_of_action`
*   `cycle` -> `peptide.cycle_duration`
*   `storage` -> `peptide.storage_temperature`
*   `molecular_information_amino_acid_sequence` -> `peptide.sequence` (if present)

### 2. Benefits (`benefits` & `peptide_benefits`)
*   `overview_key_benefits` -> Must be split by commas (or periods) into an array of individual strings/objects.
    *   **Mapping:** `peptide.benefits` -> `[ { "name": "Enhanced NAD+ levels" }, ... ]`

### 3. Side Effects (`side_effects` & `peptide_side_effects`)
*   `side_effects_and_safety_side_effects_X` (where X is 1 to 7+) -> Array of individual side effects.
    *   **Mapping:** `peptide.side_effects` -> `[ { "name": "Nausea" }, ... ]`
*   `side_effects_and_safety_when_to_stop_X` -> Merged into a text block or array for `peptide.stop_signs`.

### 4. Interactions (`peptide_interactions`)
Based on dynamic fields like: `peptide_interactions_[secondary_peptide]_[interaction_type]` (e.g., `peptide_interactions_nad+_precursors_(nmn,_nr)_synergistic`)
*   **Secondary Peptide Name**: Extracted from column name between `peptide_interactions_` and the last `_[type]`.
*   **Interaction Type**: The last suffix in the column name (e.g., `synergistic`, `compatible`).
*   **Description**: The cell's text value.
    *   **Mapping:** `peptide.interactions` -> `[ { "peptide_name_2": "NAD+ Precursors", "interaction_type": "synergistic", "description": "..." } ]`

### 5. Protocols (`peptide_protocols` umbrella)

Because a single row in the CSV usually represents a specific Peptide + Method combination, the base protocol attributes come directly from the row.
*   `Method` -> `protocol.administration_method` (e.g., "Injectable", "Oral")
*   `what_to_expect_X` -> Becomes a JSON array under `protocol.expectations` -> `[ "Week 1: Energy increase", ... ]`

#### 5.1 Reconstitution Steps (`peptide_protocol_reconstitution_steps`)
*   `how_to_reconstitute_others` -> Parsed line-by-line or by numbered steps.
    *   **Mapping:** `protocol.reconstitution_steps` -> `[ { "step_number": 1, "description": "..." } ]`

#### 5.2 Quality Indicators (`protocol_quality_indicators`)
Based on columns starting with `quality_indicators_`:
*   **Indicator Title**: The extracted end of the column name (e.g., `white_to_off-white_capsules` -> "White to off-white capsules").
*   **Description**: The cell's text value.
    *   **Mapping:** `protocol.quality_indicators` -> `[ { "indicator_title": "...", "indicator_description": "..." } ]`

#### 5.3 Application Places (`application_places` & `protocol_application_places`)
*   `route` -> Provides context for places (e.g., "Injectable (SubQ: abdomen, thigh, arm)"). Parses into places.
    *   **Mapping:** `protocol.application_places` -> `[ "abdomen", "thigh", "arm" ]`

#### 5.4 Dosages & Schedules (`dosages`, `schedules`, `protocol_dosages`)
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

### 6. Research Indications (`peptide_research_indications`)
Based on dynamic columns like: `research_indications_[category]_[tag]_([specific_indication])`
*   **Category/Indication**: Embedded in the column name (e.g., *Longevity (NAD+ Enhancement)*).
*   **Tag**: Extracted enum value (e.g., `most_effective`, `moderate`).
*   **Description**: The cell value.
    *   **Mapping:** `peptide.research_indications` -> `[ { "indication_title": "NAD+ Enhancement", "effectiveness_tag": "most_effective", "description": "..." } ]`

### 7. Research Studies & Citations (`references`)
Based on columns like: `references_research_studies_([title])`
*   **Title**: Extracted from column name between parentheses.
*   **Value (URL/Abstract)**: The cell's text value.
    *   **Mapping:** `peptide.references` -> `[ { "reference_type": "study", "title": "Muscle Function...", "abstract": "..." } ]`

### 8. Pharmacokinetics/Graph Data
*   `graph_data_json` -> Direct pass-through to a JSONB column (e.g., `pharmacokinetics_json` inside the peptide record).

---
