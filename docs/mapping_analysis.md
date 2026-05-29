# Data Mapping Analysis: Web Scraped CSV to DBML Schema

## Overview
This document provides a perspective on how the data from `output_v6.csv` ([pep_pedia_master.csv](file:///home/saif/Documents/web_scrape/output_v6/pep_pedia_master.csv)) should be mapped and inserted into the tables defined in [schema.dbml](file:///home/saif/Documents/web_scrape/peptides_temp/docs/db-diagrams/sds_schema.dbml). The goal is to ingest the scraped peptide information seamlessly into the relational database.

## Schema Matches & Data Insertion Strategy

### 1. **Core Peptide Information**
Table: `peptides`
*   `Peptide_Name` -> maps to `peptides.name` and potentially generates the `peptides.slug`.
*   `Full_Name` -> mapped to `peptides.synonyms` (or parsed into name/synonyms).
*   `molecular_information_amino_acid_sequence` -> mapped to `peptides.sequence`.
*   `cycle` -> mapped to `peptides.cycle_duration`.
*   `storage` -> mapped to `peptides.storage_temperature`.
*   `overview_what_is_[peptide]` -> mapped to `peptides.overview`.
*   `overview_mechanism_of_action` -> mapped to `peptides.mechanism_of_action`.

### 2. **Administration Methods & Application Places**
Tables: `administration_methods`, `application_places`, `protocol_application_places`
*   `Method` (e.g., Injectable, Oral) -> Insert/Lookup in `administration_methods.name`.
*   `route` (e.g., "Injectable (Belly, thigh...)" or "Oral capsules") -> Mapped to `application_places.name` and linked via `protocol_application_places` to the specific protocol.

### 3. **Protocols & Dosages**
Tables: `peptide_protocols`, `dosages`, `schedules`, `protocol_dosages`
*   The scraped data has `typical_dose`. This should be decomposed into amount/unit for `dosages.amount` and `dosages.unit`.
*   Specific protocol columns like `research_protocols_goal_1`, `research_protocols_dose_1`, `research_protocols_frequency_1`, `research_protocols_route_1`:
    *   Goal -> `peptide_protocols.name` or `peptide_protocols.description`.
    *   Dose -> `dosages` table, then linked in `protocol_dosages`.
    *   Frequency -> `schedules.frequency`, linked in `protocol_dosages`.
    *   Route -> `application_places`, linked to the protocol.

### 4. **Key Benefits**
Tables: `benefits`, `peptide_benefits`
*   `overview_key_benefits` -> Can be summarized and inserted into `peptide_protocols.key_benefits` or broken down into the `benefits` table and linked via `peptide_benefits`.

### 5. **Research Indications**
Tables: `peptide_research_indications`
*   Columns like `research_indications_wound_healing_most_effective_(tendon_healing)` -> 
    *   Indication Title: "Wound Healing (Tendon Healing)"
    *   Effectiveness Tag: `most_effective` (mapped to `effectiveness_tag` enum).
    *   Insert into `peptide_research_indications`.

### 6. **Peptide Interactions**
Table: `peptide_interactions`
*   Columns like `peptide_interactions_tb-500_synergistic` -> 
    *   Matched with a secondary peptide (e.g., TB-500).
    *   Interaction Type Enum: `synergistic`.
    *   Description: Extracted from the row text.
    *   Insert into `peptide_interactions` table indicating `peptide_id_1` and `peptide_id_2`.

### 7. **Reconstitution & Quality**
Tables: `peptide_protocol_reconstitution_steps`, `protocol_quality_indicators`
*   Columns `how_to_reconstitute_others` (like Step 1, Step 2) -> Parsed by steps and inserted into `peptide_protocol_reconstitution_steps` with `step_number`.
*   Columns `quality_indicators_white,_fluffy_cake` -> Inserted into `protocol_quality_indicators.indicator_title` and `.indicator_description`.

### 8. **What to Expect**
Table: `peptide_protocols.expectations`
*   Columns `what_to_expect_1` to `what_to_expect_5` -> Should be combined into a JSON array and inserted directly into the JSONB field `peptide_protocols.expectations`.

### 9. **Side Effects & Discontinuation**
Tables: `side_effects`, `peptide_side_effects`
*   `side_effects_and_safety_side_effects_X` -> Insert/lookup in `side_effects.name` and link via `peptide_side_effects`.
*   `side_effects_and_safety_when_to_stop_X` -> Can be stored in `peptides.stop_signs` as a comma-separated list or JSON.

### 10. **Research Studies & References**
Tables: `research_studies`, `citations`, `peptide_references`
*   Columns `references_research_studies_(...)` -> Insert into `research_studies.title`, `url`, `abstract`, and then link via `peptide_references` with `reference_type` = 'study'.
*   Columns `references_citations_X` -> Insert into `citations.title` or `publication_url` and link via `peptide_references` with `reference_type` = 'citation'.

### 11. **Graph Data JSON**
The `graph_data_json` which holds PK data over 24h, 7d, 14d, 30d should likely be inserted into a raw JSONB column. Note: I do not see a dedicated `pharmacokinetics` JSON field in `peptides`, but it might be suitable to add such a column or store it in an associated external file/DB structure.

## Summary of Execution Perspective
1. **Scripting Migration**: Ensure the migration script loops through the CSV row by row, ensuring all dependent entities mapping (like Enums, Administration Methods) are satisfied or inserted first (lookup or insert constraint).
2. **Entity Resolution**: Data like Peptide Name and Secondary Interactions require pre-existing rows. Wait to populate `peptide_interactions` until *after* all peptides are inserted into the `peptides` table to safely resolve foreign key constraints on `peptide_id_2`.
3. **Array Flattening**: Repeated columns such as protocols (1, 2, 3...) should map correctly to a `1-to-many` relationship (e.g., one BPC-157 row leads to 4 inserts on `peptide_protocols`).
