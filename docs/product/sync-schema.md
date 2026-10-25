# Sync schema: insert order, entity relations and field mapping

One document for how a scraped CSV row becomes rows of the platform's tables (XR-8). The platform's Drizzle schema owns the tables; this service only writes them.

- [Insert order](#part-1-insert-order)
- [Entity relations](#part-2-entity-relations)
- [CSV column to table column](#part-3-csv-column-to-table-column)

---

## Part 1: Insert order

This document defines the relational structure and the required insertion order for the `peptides` database to preserve referential integrity.

### 1. Insertion Hierarchy

To maintain foreign key constraints, data must be inserted in the following order:

#### Group A: Independent Lookup Tables
These tables have no dependencies on other entities (or only self-reference).
1.  **`categories`**: Peptide categories (supports hierarchical structure via `parent_category_id`).
2.  **`administration_methods`**: Methods of use (Injectable, Oral, etc.).
3.  **`benefits`**: General benefits (Muscle Growth, Recovery, etc.).
4.  **`side_effects`**: Potential side effects.
5.  **`dosages`**: Base dosage units and amounts.
6.  **`schedules`**: Frequency and timing schedules.
7.  **`application_places`**: Body locations for application.
8.  **`research_studies`** / **`citations`**: External references.

#### Group B: Core Entities
9.  **`peptides`**: The central record. Depends on `categories` (category_id).

#### Group C: Peptide-Specific Relations
These tables link directly to the peptide.
10. **`peptide_benefits`**: Links `peptides` to `benefits`.
11. **`peptide_side_effects`**: Links `peptides` to `side_effects`.
12. **`peptide_interactions`**: Links `peptides` to other peptides (or names).
13. **`peptide_research_indications`**: Specific research categories for a peptide.
14. **`peptide_references`**: Links `peptides` to `research_studies`.

#### Group D: Protocol Structure
15. **`peptide_protocols`**: Defines a specific use protocol. Depends on `peptides` and `administration_methods`.

#### Group E: Protocol Details
16. **`peptide_protocol_reconstitution_steps`**: Steps to prepare the peptide. Depends on `peptide_protocols`.
17. **`protocol_application_places`**: Junction between `peptide_protocols` and `application_places`.
18. **`protocol_quality_indicators`**: Verification steps. Depends on `peptide_protocols`.
19. **`protocol_dosages`**: The actual dosage plan. Depends on `peptide_protocols`, `dosages`, and `schedules`.

#### Group F: Dosage Context
20. **`protocol_dosage_benefits`**: Benefits linked to a specific protocol dose. Depends on `protocol_dosages` and `benefits`.
21. **`protocol_dosage_side_effects`**: Side effects linked to a specific protocol dose. Depends on `protocol_dosages` and `side_effects`.
22. **`peptide_research_indication_studies`**: Links an indication to a study. Depends on `peptide_research_indications` and `research_studies`.

---

### 2. Table Value Relationships & Constraints

| Table Name | Linkage (Foreign Key) | Key Values / Columns |
| :--- | :--- | :--- |
| `peptides` | `category_id` -> `categories(id)` | `name`, `slug`, `overview`, `mechanism_of_action`, `sequence` |
| `peptide_protocols` | `peptide_id`, `administration_method_id` | `name`, `expectations` (JSONB), `best_timing` |
| `peptide_benefits` | `peptide_id`, `benefit_id` | `general_potency`, `general_evidence_level` |
| `peptide_interactions` | `peptide_id_1`, `peptide_id_2` (opt) | `interaction_type` (Enum), `severity`, `description` |
| `protocol_dosages` | `protocol_id`, `dosage_id`, `schedule_id` | `is_default`, `notes`, `sort_order` |
| `protocol_application_places` | `protocol_id`, `application_place_id` | Junction table |

---

### 3. Data Mapping Guidance

*   **Dictionaries**: Before inserting core data, ensure lookup tables (`benefits`, `side_effects`, etc.) are populated or checked for existing names to retrieve IDs.
*   **JSONB Fields**: Columns like `expectations`, `quick_start_guide`, and `pharmacokinetics_json` contain structured nested data.
*   **Enums**: Fields like `interaction_type`, `fda_approval_status`, and `wada_status` use custom types. Values must match the DB definitions.

---

## Part 2: Entity relations

This document outlines the relational structure of the database based on the DBML schema, demonstrating how the raw scraped data should be normalized and mapped into the relational database.

### Core Entities
1. **Peptides** (`peptides`)
   - The central entity in the schema.
   - Primary Key: `id`

2. **Administration Methods** (`administration_methods`) 
   - Stores distinct methods (e.g., Injectable, Oral, Topical).
   - Primary Key: `id`
   - Relates to Peptides via Protocols.

### Relational Linkages & Hierarchy

#### 1. Peptide Level Relations
- **Benefits**: `peptide_benefits` links directly to `benefits`.
- **Side Effects**: `peptide_side_effects` links directly to `side_effects`.
- **Interactions**: `peptide_interactions` links to other peptides (by ID or name).
- **Research Indications**: `peptide_research_indications` identifies use cases.
- **References**: `peptide_references` links to `research_studies` or `citations`.

#### 2. Protocol Hierarchy (`peptide_protocols`)
The protocol is a specific use-case for a peptide via an administration method.
- **Core**: `peptides` + `administration_methods` -> `peptide_protocols`.
- **Protocol Children ("Protocols Others")**:
    - **Reconstitution**: `peptide_protocol_reconstitution_steps` (Step-by-step mixing).
    - **Quality**: `protocol_quality_indicators` (Verify product integrity).
    - **Application**: `protocol_application_places` (Junction to `application_places`).
    - **Research Context**: `peptide_research_indication_studies` (Links a specific indication to this protocol and a study).

#### 3. Dosage & Benefit Hierarchy
- **Dosages**: `protocol_dosages` (Specific dose instances for a protocol).
    - **Dosage Benefits**: `protocol_dosage_benefits` (Benefits achieved *at this specific dose*).
    - **Dosage Side Effects**: `protocol_dosage_side_effects` (Side effects likely *at this specific dose*).

---

### Processing Flow Recommendation for Scraped Data

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

#### Dependency Insertion Order
To maintain referential integrity, inserts must follow this hierarchy (detailed in [Part 1](#part-1-insert-order)):
1.  **Lookups**: `categories`, `administration_methods`, `benefits`, `side_effects`, `dosages`, `schedules`, `application_places`, `research_studies`.
2.  **Core**: `peptides`.
3.  **Peptide Bridges**: `peptide_benefits`, `peptide_side_effects`, `peptide_interactions`, `peptide_research_indications`, `peptide_references`.
4.  **Protocols**: `peptide_protocols`.
5.  **Protocol Details**: `peptide_protocol_reconstitution_steps`, `protocol_application_places`, `protocol_quality_indicators`, `protocol_dosages`.
6.  **Dosage/Study Context**: `protocol_dosage_benefits`, `protocol_dosage_side_effects`, `peptide_research_indication_studies`.

---

### Scraped CSV to JSON payload mapping

This document maps the columns found in the scraped CSV (e.g., `output_v6/pep_pedia_master.csv`) to the hierarchical JSON payload structure defined above. This payload matches the required dependencies and ordering for insertion into the database schema.

#### 1. Top-Level Peptide Entity (`peptides`)

*   `Peptide_Name` -> `peptide.name`
*   `Full_Name` -> `peptide.synonyms`
*   `overview_what_is_[peptide]` (dynamic match) -> `peptide.overview`
*   `overview_mechanism_of_action` -> `peptide.mechanism_of_action`
*   `cycle` -> `peptide.cycle_duration`
*   `storage` -> `peptide.storage_temperature`
*   `molecular_information_amino_acid_sequence` -> `peptide.sequence` (if present)

#### 2. Benefits (`benefits` & `peptide_benefits`)
*   `overview_key_benefits` -> Must be split by commas (or periods) into an array of individual strings/objects.
    *   **Mapping:** `peptide.benefits` -> `[ { "name": "Enhanced NAD+ levels" }, ... ]`

#### 3. Side Effects (`side_effects` & `peptide_side_effects`)
*   `side_effects_and_safety_side_effects_X` (where X is 1 to 7+) -> Array of individual side effects.
    *   **Mapping:** `peptide.side_effects` -> `[ { "name": "Nausea" }, ... ]`
*   `side_effects_and_safety_when_to_stop_X` -> Merged into a text block or array for `peptide.stop_signs`.

#### 4. Interactions (`peptide_interactions`)
Based on dynamic fields like: `peptide_interactions_[secondary_peptide]_[interaction_type]` (e.g., `peptide_interactions_nad+_precursors_(nmn,_nr)_synergistic`)
*   **Secondary Peptide Name**: Extracted from column name between `peptide_interactions_` and the last `_[type]`.
*   **Interaction Type**: The last suffix in the column name (e.g., `synergistic`, `compatible`).
*   **Description**: The cell's text value.
    *   **Mapping:** `peptide.interactions` -> `[ { "peptide_name_2": "NAD+ Precursors", "interaction_type": "synergistic", "description": "..." } ]`

#### 5. Protocols (`peptide_protocols` umbrella)

Because a single row in the CSV usually represents a specific Peptide + Method combination, the base protocol attributes come directly from the row.
*   `Method` -> `protocol.administration_method` (e.g., "Injectable", "Oral")
*   `what_to_expect_X` -> Becomes a JSON array under `protocol.expectations` -> `[ "Week 1: Energy increase", ... ]`

##### 5.1 Reconstitution Steps (`peptide_protocol_reconstitution_steps`)
*   `how_to_reconstitute_others` -> Parsed line-by-line or by numbered steps.
    *   **Mapping:** `protocol.reconstitution_steps` -> `[ { "step_number": 1, "description": "..." } ]`

##### 5.2 Quality Indicators (`protocol_quality_indicators`)
Based on columns starting with `quality_indicators_`:
*   **Indicator Title**: The extracted end of the column name (e.g., `white_to_off-white_capsules` -> "White to off-white capsules").
*   **Description**: The cell's text value.
    *   **Mapping:** `protocol.quality_indicators` -> `[ { "indicator_title": "...", "indicator_description": "..." } ]`

##### 5.3 Application Places (`application_places` & `protocol_application_places`)
*   `route` -> Provides context for places (e.g., "Injectable (SubQ: abdomen, thigh, arm)"). Parses into places.
    *   **Mapping:** `protocol.application_places` -> `[ "abdomen", "thigh", "arm" ]`

##### 5.4 Dosages & Schedules (`dosages`, `schedules`, `protocol_dosages`)
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

#### 6. Research Indications (`peptide_research_indications`)
Based on dynamic columns like: `research_indications_[category]_[tag]_([specific_indication])`
*   **Category/Indication**: Embedded in the column name (e.g., *Longevity (NAD+ Enhancement)*).
*   **Tag**: Extracted enum value (e.g., `most_effective`, `moderate`).
*   **Description**: The cell value.
    *   **Mapping:** `peptide.research_indications` -> `[ { "indication_title": "NAD+ Enhancement", "effectiveness_tag": "most_effective", "description": "..." } ]`

#### 7. Research Studies & Citations (`references`)
Based on columns like: `references_research_studies_([title])`
*   **Title**: Extracted from column name between parentheses.
*   **Value (URL/Abstract)**: The cell's text value.
    *   **Mapping:** `peptide.references` -> `[ { "reference_type": "study", "title": "Muscle Function...", "abstract": "..." } ]`

#### 8. Pharmacokinetics/Graph Data
*   `graph_data_json` -> Direct pass-through to a JSONB column (e.g., `pharmacokinetics_json` inside the peptide record).

---

---

## Part 3: CSV column to table column

> **Generated:** 2026-07-01
> **Purpose:** Comprehensive reference for how scraped CSV columns map to database tables during the sync pipeline.
> **Pipeline Flow:** Scrape → CSV → `DbImportOrchestrator` / `GraphImportOrchestrator` → Database

---

### Table of Contents

1. [Lookup Tables (Group A)](#1-lookup-tables-group-a)
2. [Peptides Core Table (Group B)](#2-peptides-core-table-group-b)
3. [Relation / Junction Tables (Group C)](#3-relation--junction-tables-group-c)
4. [Protocol Tables (Group D + E)](#4-protocol-tables-group-d--e)
5. [Graph Table (Group D)](#5-graph-table-group-d)
6. [Method Keyword Mapping](#6-method-keyword-mapping)
7. [Sync Pipeline Overview](#7-sync-pipeline-overview)

---

### 1. Lookup Tables (Group A)

#### `administration_methods`

Stores administration/route methods (e.g. Injectable, Capsule, Nasal Spray).

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `name` | `Method` (first keyword-mapped → canonical name) | `"Injectable"` |
| 3 | `description` | `Method` (auto-generated) | `"Injectable administration method"` |

**Mapper:** `AdministrationMethodMapper` (`app/services/sync/group_a/lookup_mappers.py`)

**Notes:** CSV `Method` goes through keyword mapping before insertion (e.g. `"Nasal"` → `"Nasal Spray"`). See [Method Keyword Mapping](#6-method-keyword-mapping).

---

#### `benefits`

Stores general benefit descriptions.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `name` | `overview_key_benefits` (split by `.`) | `"Direct systemic delivery for cardiac tissue support"` |
| 3 | `description` | `overview_key_benefits` (same as name) | `"Direct systemic delivery for cardiac tissue support, established reconstitution protocols..."` |

**Mapper:** `BenefitMapper` (`app/services/sync/group_a/lookup_mappers.py`)
**Logic:** Splits `overview_key_benefits` by periods into multiple benefit entries.

---

#### `side_effects`

Stores potential side effects.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `name` | `side_effects_and_safety_side_effects_{1..9}` (split by `.`) | `"Nausea"` |
| 3 | `description` | `side_effects_and_safety_side_effects_{1..9}` (same as name) | `"Nausea"` |

**Mapper:** `SideEffectMapper` (`app/services/sync/group_a/lookup_mappers.py`)
**Logic:** Iterates `side_effects_and_safety_side_effects_1` through `_9`, splits each by periods.

---

#### `schedules`

Stores frequency and timing schedules.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `name` | `research_protocols_frequency_{1..5}` | `"Every 3-7 days"` |
| 3 | `frequency` | `research_protocols_frequency_{1..5}` (same as name) | `"Every 3-7 days"` |

**Mapper:** `ScheduleMapper` (`app/services/sync/group_a/lookup_mappers.py`)
**Logic:** Iterates `research_protocols_frequency_1` through `_5`.

---

#### `dosages`

Stores dosage amounts and units.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `name` | Auto-generated from amount + unit | `"10-20mg"` |
| 3 | `amount` | `typical_dose` / `research_protocols_dose_{1..5}` (parsed) | `"10-20"` |
| 4 | `unit` | `typical_dose` / `research_protocols_dose_{1..5}` (parsed) | `"mg"` |

**Mapper:** `DosageMapper` (`app/services/sync/group_a/lookup_mappers.py`)
**Parser:** `parse_dosage_string()` — extracts numeric amount and unit suffix. Examples:
- `"100 mcg"` → amount=`"100"`, unit=`"mcg"`
- `"10-20mg (Every 3-7 days)"` → amount=`"10-20"`, unit=`"mg"`
- `"~5mg/kg/day"` → amount=`"5"`, unit=`"mg/kg/day"`

---

#### `application_places`

Stores injection/application sites.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `name` | `route` or `research_protocols_route_{1..5}` | `"Injectable (Subcutaneous: abdomen, thigh, upper arm)"` |

**Mapper:** `ApplicationPlaceMapper` (`app/services/sync/group_e/detail_mappers.py`)
**Logic:** Takes the route string as the application place name (truncated to 100 chars).

---

#### `research_studies`

Stores external research studies.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `title` | `references_research_studies_{key}` (parsed from column name) | `"Cardiogen Preclinical Study"` |
| 3 | `url` | `references_research_studies_{key}` (if value starts with `http`) | `"https://pubmed.ncbi.nlm.nih.gov/..."` |
| 4 | `abstract` | `references_research_studies_{key}` (if value does NOT start with `http`) | `"Study on cardiac tissue repair..."` |

**Mapper:** `ResearchStudyMapper` (`app/services/sync/group_a/lookup_mappers.py`)

---

#### `citations`

Stores academic citations with DOIs.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `title` | `references_citations_{key}` (parsed from text) | `"Effects of AEDR on cardiomyocyte apoptosis"` |
| 3 | `doi` | `references_citations_{key}` (extracted via regex `DOI:\s*(10.\d{4,9}/...)`) | `"10.1007/s10517-020-04825-6"` |
| 4 | `authors` | `references_citations_{key}` (parsed via regex `^(.*?)\(\d{4}\)\.`) | `"Khavinson V.Kh., et al."` |
| 5 | `publication_url` | `references_citations_{key}` (if starts with `http`) | `"https://pubmed.ncbi.nlm.nih.gov/..."` |
| 6 | `abstract` | `references_citations_{key}` (full cleaned text) | `"Full citation text including abstract..."` |

**Mapper:** `ResearchStudyMapper` (`app/services/sync/group_a/lookup_mappers.py`)
**Logic:** Cleans "View Publication" text, extracts DOI via regex, extracts authors before `(Year).`.

---

### 2. Peptides Core Table (Group B)

#### `peptides`

The central peptide record — one row per peptide.

| # | DB Column | CSV Source Field | Example Value (Cardiogen) |
|---|-----------|-----------------|---------------------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `42` |
| 2 | `name` | `Peptide_Name` | `"Cardiogen"` |
| 3 | `slug` | Auto-generated from `Peptide_Name` (lowercased, hyphenated) | `"cardiogen"` |
| 4 | `synonyms` | `Full_Name` | `"Cardiac Bioregulatory Tetrapeptide \| Cardiovascular & Tissue Repair"` |
| 5 | `overview` | `overview_what_is_{slug}` (dynamic column) | `"Cardiogen (Ala-Glu-Asp-Arg / AEDR) is a synthetic tetrapeptide bioregulator..."` |
| 6 | `mechanism_of_action` | `overview_mechanism_of_action` | `"Subcutaneous injection provides systemic distribution allowing AEDR tetrapeptide to reach cardiac tissue..."` |
| 7 | `sequence` | `molecular_information_amino_acid_sequence` | `"Ala-Glu-Asp-Arg (AEDR)"` |
| 8 | `cycle_duration` | `cycle` | `"2-4 weeks (Typical duration)"` |
| 9 | `storage_temperature` | `storage` | `"2-8°C (Refrigerated)"` |
| 10 | `fda_approval_status` | `fda_approval_status` | `null` or `"investigational"` |
| 11 | `wada_status` | `wada_status` | `null` or `"banned"` |
| 12 | `stop_signs` | `side_effects_and_safety_when_to_stop_{suffix}` (multiple columns) | `["If severe reaction occurs", "If symptoms persist"]` |
| 13 | `key_information` | `overview_key_benefits` | `"Direct systemic delivery for cardiac tissue support..."` |

**Mapper:** `PeptideMapper` (`app/services/sync/group_b/peptide_mapper.py`)
**Slug generation:** `re.sub(r'[^a-z0-9]+', '-', raw_name.lower()).strip('-')`
**Dynamic overview column:** Tries `overview_what_is_{slug}` first, falls back to first `overview_what_is_*` column found.

---

### 3. Relation / Junction Tables (Group C)

#### `peptide_benefits`

Links peptides to their benefits.

| # | DB Column | Source | Example Value |
|---|-----------|--------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `peptide_id` | Resolved from `peptides.id` (via slug match) | `42` |
| 3 | `benefit_id` | Resolved from `benefits.id` (via `benefit_name` lookup) | `7` |

**CSV Source:** `overview_key_benefits` (split by `.`)
**Mapper:** `RelationMapper._map_benefits()` (`app/services/sync/group_c/relation_mappers.py`)

---

#### `peptide_side_effects`

Links peptides to their side effects.

| # | DB Column | Source | Example Value |
|---|-----------|--------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `peptide_id` | Resolved from `peptides.id` | `42` |
| 3 | `side_effect_id` | Resolved from `side_effects.id` | `15` |

**CSV Source:** `side_effects_and_safety_side_effects_{1..9}`
**Mapper:** `RelationMapper._map_side_effects()` (`app/services/sync/group_c/relation_mappers.py`)

---

#### `peptide_interactions`

Captures interactions between peptides.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `peptide_id_1` | Resolved from `peptides.id` (current peptide) | `42` |
| 3 | `peptide_id_2` | Resolved lookup (if exists) or `null` | `null` |
| 4 | `peptide_name_2` | Parsed from column name `peptide_interactions_{name}_{type}` | `"Bpc 157"` |
| 5 | `interaction_type` | Last segment of column name after `peptide_interactions_{name}_` | `"synergistic"` |
| 6 | `description` | Cell value | `"May enhance tissue repair effects"` |

**CSV Column Pattern:** `peptide_interactions_{peptide_name}_{interaction_type}`
**Example CSV Column:** `peptide_interactions_bpc-157_synergistic`
**Mapper:** `RelationMapper._map_interactions()` (`app/services/sync/group_c/relation_mappers.py`)
**Logic:** Column name is parsed: middle part = secondary peptide name, last part = interaction type (`synergistic`, `antagonistic`, `compatible`, `monitor_combination`, etc.).

---

#### `peptide_research_indications`

Maps research indications/tags to peptides.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `peptide_id` | Resolved from `peptides.id` | `42` |
| 3 | `indication_title` | Parsed from column name `research_indications_{category}_{tag}({specific})` | `"Cardiovascular Most Effective (Cardiac Tissue Support)"` |
| 4 | `effectiveness_tag` | Parsed from column name tag segment | `"most_effective"` |
| 5 | `description` | Cell value | `"Preclinical models suggest cardiomyocyte proliferation stimulation..."` |

**CSV Column Pattern:** `research_indications_{category}_{effectiveness_tag}_({specific_area})`
**Example CSV Columns:**
- `research_indications_cardiovascular_most_effective_(cardiac_tissue_support)`
- `research_indications_cellular_effective_(cytoskeletal_protein_upregulation)`
- `research_indications_anti_aging_moderate_(geroprotective_potential)`

**Effectiveness Tags:** `most_effective`, `effective`, `moderate`
**Mapper:** `RelationMapper._map_indications()` (`app/services/sync/group_c/relation_mappers.py`)

---

#### `peptide_references`

Links peptides to research studies and citations.

| # | DB Column | Source | Example Value |
|---|-----------|--------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `peptide_id` | Resolved from `peptides.id` | `42` |
| 3 | `reference_type` | Determined by CSV column prefix | `"study"` or `"citation"` |
| 4 | `study_id` | From `research_studies.id` (if type=study) | `3` |
| 5 | `citation_id` | From `citations.id` (if type=citation) | `5` |

**CSV Source Columns:**
- `references_research_studies_{key}` → type=`"study"`
- `references_citations_{key}` → type=`"citation"`
**Mapper:** `RelationMapper._map_references()` → `ResearchStudyMapper` (`app/services/sync/group_c/relation_mappers.py`)

---

### 4. Protocol Tables (Group D + E)

#### `peptide_protocols`

Each protocol represents a specific administration protocol for a peptide.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `peptide_id` | Resolved from `peptides.id` | `42` |
| 3 | `administration_method_id` | Resolved from `administration_methods.id` via `Method` | `1` |
| 4 | `name` | `research_protocols_goal_{1..5}` (research protocol) or `Method` (default) | `"Cardiac tissue support protocol"` |
| 5 | `description` | First `overview_what_is_*` column | `"Cardiogen is a synthetic tetrapeptide..."` |
| 6 | `expectations` | `what_to_expect_{1..5}` (JSON array) | `["Gradual improvement in cardiac function", "Noticeable effects within 2-4 weeks"]` |
| 7 | `quick_start_guide` | `how_to_take_others` / `how_to_reconstitute_others` / `quick_start_guide` (JSON array) | `["Use bacteriostatic water (BAC)", "Sterile technique is essential"]` |
| 8 | `key_benefits` | `overview_key_benefits` | `"Direct systemic delivery for cardiac support..."` |
| 9 | `mechanism_of_action` | `overview_mechanism_of_action` | `"Subcutaneous injection provides systemic distribution..."` |
| 10 | `best_timing` | `best_timing` | `"Morning administration recommended"` |
| 11 | `effects_timeline` | `effects_timeline` | `"Days 1-7: Initial effects, Weeks 2-4: Peak effects"` |

**Mapper:** `ProtocolMapper` (`app/services/sync/group_d/protocol_mapper.py`)
**Logic:** Creates one protocol per research protocol entry (`research_protocols_goal_{i}` with matching `dose`, `frequency`, `route`), plus a default baseline protocol if no goals exist but `typical_dose` or `route` is present.

---

#### `peptide_protocol_reconstitution_steps`

Numbered steps for reconstituting the peptide.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `protocol_id` | Resolved from `peptide_protocols.id` | `1` |
| 3 | `step_number` | `how_to_reconstitute_others` (parsed numeric markers) | `1` |
| 4 | `description` | `how_to_reconstitute_others` (text after step number) | `"Draw 1ml of bacteriostatic water into syringe"` |

**Mapper:** `ReconstitutionMapper` (`app/services/sync/group_e/detail_mappers.py`)
**Logic:** Splits `how_to_reconstitute_others` by newlines, detects numeric markers as step numbers.

---

#### `protocol_quality_indicators`

Quality indicators for the protocol.

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `protocol_id` | Resolved from `peptide_protocols.id` | `1` |
| 3 | `indicator_title` | `quality_indicators_{key}` (column name humanized) | `"White lyophilized powder"` |
| 4 | `indicator_description` | Cell value of `quality_indicators_{key}` | `"Product should appear as white lyophilized powder"` |

**CSV Column Pattern:** `quality_indicators_{descriptive_name}`
**Example CSV Columns:** `quality_indicators_white_lyophilized_powder`, `quality_indicators_clear_reconstituted_solution`
**Mapper:** `QualityMapper` (`app/services/sync/group_e/detail_mappers.py`)

---

#### `protocol_application_places`

Links protocols to application places.

| # | DB Column | Source | Example Value |
|---|-----------|--------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `protocol_id` | Resolved from `peptide_protocols.id` | `1` |
| 3 | `application_place_id` | Resolved from `application_places.id` via route string | `3` |

**CSV Source:** `route` or `research_protocols_route_{1..5}`
**Mapper:** `ApplicationPlaceMapper` (`app/services/sync/group_e/detail_mappers.py`)

---

#### `protocol_dosages`

Links protocols to dosages and schedules.

| # | DB Column | Source | Example Value |
|---|-----------|--------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `protocol_id` | Resolved from `peptide_protocols.id` | `1` |
| 3 | `dosage_id` | Resolved from `dosages.id` (via amount+unit) | `5` |
| 4 | `schedule_id` | Resolved from `schedules.id` (via frequency) | `3` |
| 5 | `is_default` | `True` for first dosage protocol, `False` otherwise | `true` |
| 6 | `notes` | `research_protocols_dose_{i}` + `research_protocols_frequency_{i}` | `"Amount: 10-20mg, Freq: Every 3-7 days"` |

**CSV Source:** `research_protocols_dose_{1..5}` + `research_protocols_frequency_{1..5}`, fallback: `typical_dose`
**Mapper:** `ProtocolDosageMapper` (`app/services/sync/group_e/detail_mappers.py`)

---

### 5. Graph Table (Group D)

#### `peptide_graph`

Pharmacokinetics graph data (concentration curves over time).

| # | DB Column | CSV Source Field | Example Value |
|---|-----------|-----------------|---------------|
| 1 | `id` | Auto-generated (SERIAL PK) | `1` |
| 2 | `peptide_id` | Resolved from `peptides.id` (via slug match) | `42` |
| 3 | `administration_method_id` | `Method` (via keyword mapping → DB lookup) | `1` |
| 4 | `action_type` | Hardcoded as `"scraped"` or `"manual"` | `"scraped"` |
| 5 | `time_range` | `graph_data_json` → JSON key | `"24h"` |
| 6 | `peak_concentration` | `graph_data_json` → `[time_range].peak` or `[time_range].metadata.peak` | `"1 hr"` |
| 7 | `half_life` | `graph_data_json` → `[time_range].half_life` or `[time_range].metadata.half_life` | `"2.7 hrs"` |
| 8 | `cleared_percentage` | `graph_data_json` → `[time_range].cleared` or `[time_range].metadata.cleared` | `"~13.5 hrs"` |
| 9 | `path_data` | `graph_data_json` → `[time_range].path_data` (SVG path `d` attribute) | `"M 10 35 C 10.258 35..."` |
| 10 | `points` | `graph_data_json` → `[time_range].points` (JSONB) | `[{"x": 10.0, "y": 35.0}]` |
| 11 | `markers` | `graph_data_json` → `[time_range].markers` (JSONB) | `[{"cx": 41.82, "cy": 20.60, "r": 0.7, "fill": "#f59e0b"}]` |
| 12 | `x_axis_labels` | `graph_data_json` → `[time_range].x_axis_labels` or `[time_range].x_labels` (JSONB) | `[{"pos": 10.0, "label": "Dose"}]` |
| 13 | `y_axis_labels` | `graph_data_json` → `[time_range].y_axis_labels` or `[time_range].y_labels` (JSONB) | `[{"pos": 8.0, "label": "100%"}]` |
| 14 | `legend` | `graph_data_json` → `[time_range].legend` (JSONB) | `{"peak": "rgb(34, 197, 94)", "half-life": "rgb(245, 158, 11)"}` |

**CSV Column:** `graph_data_json` — a single JSON column containing all graph data.
**Mapper:** `GraphMapper` (`app/services/sync/group_d/graph_mapper.py`)
**Graph CSV:** Only `pep_pedia_graph.csv` contains the `graph_data_json` column.
**Input Formats:** Supports two JSON formats:
1. **Src pipeline format** (via `csv_storage.py` → `dataclasses.asdict()`): keys at root level
2. **Graph/scraper.py format** (from web scraper): metadata nested under `"metadata"`, labels use `"text"` key

---

### 6. Method Keyword Mapping

The `Method` CSV field contains raw scraped values that are mapped to canonical DB names before insertion:

| CSV Keyword (from `Method`) | Canonical DB Name |
|----------------------------|-------------------|
| `nasal` / `intranasal` | `Nasal Spray` |
| `topical` | `Topical Cream` |
| `oral` | `Capsule` |
| `injectable` | `Injectable` |

**Defined in:** `app/services/sync/method_resolution.py` (`METHOD_KEYWORD_MAP`, `resolve_method`; shared by the core sync and the evaluation builder; `GraphImportOrchestrator` keeps its own exact-match map). The first comma-separated part that maps to a method the DB has wins; extra keywords (`subcutaneous`, `capsule`, `cream`, ...) are in the module.
**Purpose:** An unresolved `Method` (empty, no keyword, or the canonical name missing from `administration_methods`) no longer skips the peptide (AID-4). The peptide columns and every child that needs no method (benefits, side effects, interactions, indications, references) are written; only the **protocols** are left out, because they need an `administration_methods` id. The job result lists each such peptide in `partial_peptides` (`name`, `slug`, `reason`, `not_written`). A peptide with no matching `peptides` row is still skipped.

**Columns the peptide mapper fills from pep-pedia:** besides the original ones, `half_life_value`/`half_life_unit` (parsed from text such as "4 hrs"), `effect_onset`, `break_period`, `required_materials`, `safety_guidelines`, `quality_checks`. pep-pedia's research maturity label (`research_level` in the CSV) is returned in each `synced_peptides` entry as `research_stage` and is **not** written: `peptides.research_level` is the development-phase enum. A `research_stage` column is AWD-16.

---

### 7. Sync Pipeline Overview

#### Core Sync (`POST /sync/core`)

```
URLs → Scrape (CORE_ONLY mode) → pep_pedia_enhanced.csv → DbImportOrchestrator
                                                              │
                        ┌─────────────────────────────────────┤
                        ▼                                     ▼
                  Group A (Lookups)                    Group B (Peptide)
                  ────────────────                     ────────────────
                  administration_methods               peptides
                  benefits
                  side_effects                         Group C (Relations)
                  schedules                             ─────────────────
                  dosages                               peptide_benefits
                  application_places                    peptide_side_effects
                  research_studies                      peptide_interactions
                  citations                             peptide_research_indications
                                                        peptide_references
                        │
                        ▼
                  Group D+E (Protocols)
                  ────────────────────
                  peptide_protocols
                  peptide_protocol_reconstitution_steps
                  protocol_quality_indicators
                  protocol_application_places
                  protocol_dosages
```

#### Graph Sync (`POST /sync/graph`)

```
URLs → Scrape (GRAPH_ONLY mode) → pep_pedia_graph.csv → GraphImportOrchestrator
                                                          │
                                                          ▼
                                                    Group D (Graph)
                                                    ──────────────
                                                    peptide_graph
```

#### Graph-Missing Sync (`POST /sync/graph-missing`)

Same as Graph Sync, but only injects graph data for `administration_method_id` combinations that do **not** already exist for that peptide.

---

### Appendix: CSV File Reference

#### `output_dir/pep_pedia_enhanced.csv`

Used by **Core Sync**. Contains all peptide data fields.

**Key Column Groups:**
- Identity: `Peptide_Name`, `Full_Name`, `Method`, `URL`
- Basic: `typical_dose`, `route`, `cycle`, `storage`
- Overview: `overview_what_is_{slug}`, `overview_key_benefits`, `overview_mechanism_of_action`
- Molecular: `molecular_information_amino_acid_sequence`
- Research Indications: `research_indications_{category}_{tag}_{area}`
- Research Protocols: `research_protocols_goal_{i}`, `research_protocols_dose_{i}`, `research_protocols_frequency_{i}`, `research_protocols_route_{i}`
- Interactions: `peptide_interactions_{name}_{type}`
- Reconstitution: `how_to_reconstitute_others`
- Quality: `quality_indicators_{name}`
- Expectations: `what_to_expect_{1..5}`
- Side Effects: `side_effects_and_safety_side_effects_{1..9}`, `side_effects_and_safety_when_to_stop_{suffix}`
- References: `references_research_studies_{key}`, `references_citations_{key}`
- FDA/WADA: `fda_approval_status`, `wada_status`

#### `output_dir/pep_pedia_graph.csv`

Used by **Graph Sync**. Contains identity fields + graph JSON data.

**Columns:** `Peptide_Name`, `Full_Name`, `Method`, `URL`, `typical_dose`, `route`, `cycle`, `storage`, `graph_data_json`

