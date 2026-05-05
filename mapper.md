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

## Relational Linkages & Junction Tables

### Protocols (Peptides + Administration Methods)
- **Table**: `peptide_protocols`
- **Relations**: 
  - `peptide_id` -> `peptides.id`
  - `administration_method_id` -> `administration_methods.id`
- **Purpose**: Defines a specific use-case or "protocol" for a peptide using a specific administration method. An injectable protocol for BPC-157 is distinct from an oral protocol.

### Protocol Dosages & Schedules
- **Tables**: `dosages`, `schedules`
- **Junction Table**: `protocol_dosages`
- **Relations**:
  - `protocol_id` -> `peptide_protocols.id`
  - `dosage_id` -> `dosages.id`
  - `schedule_id` -> `schedules.id`
- **Purpose**: A single protocol can have multiple dosages and schedules (e.g., standard dose, loading dose).

### Benefits
- **Table**: `benefits`
- **Junction Tables**: 
  - **`peptide_benefits`**: Links `peptide_id` directly to `benefit_id`. (General benefits of the peptide).
  - **`protocol_dosage_benefits`**: Links `protocol_dosage_id` to `benefit_id`. (Benefits specific to a certain dose in a protocol).

### Side Effects
- **Table**: `side_effects`
- **Junction Tables**:
  - **`peptide_side_effects`**: Links `peptide_id` to `side_effect_id`. (General side effects).
  - **`protocol_dosage_side_effects`**: Links `protocol_dosage_id` to `side_effect_id` (often with a likelihood enum). (Side effects specific to a dose).

### Application Places (e.g., SubQ Belly, Intramuscular Thigh)
- **Table**: `application_places`
- **Junction Table**: `protocol_application_places`
- **Relations**:
  - `protocol_id` -> `peptide_protocols.id`
  - `application_place_id` -> `application_places.id`

### Reconstitution & Quality Indicators
- **Tables**: `peptide_protocol_reconstitution_steps`, `protocol_quality_indicators`
- **Relations**: Both contain a `protocol_id` that maps back to `peptide_protocols.id`.
- **Purpose**: Protocol-specific steps to mix/reconstitute, and indicators to verify quality dynamically.

### Peptide Interactions
- **Table**: `peptide_interactions`
- **Relations**: 
  - `peptide_id_1` -> `peptides.id`
  - `peptide_id_2` -> `peptides.id` (Optional foreign key, often paired with `peptide_name_2` if the second peptide does not exist in the DB).
- **Purpose**: Maps synergistic or antagonistic interactions between two peptides.

### Research Indications, Studies & Citations
- **Tables**: `research_studies`, `citations`
- **Junction Tables**: 
  - **`peptide_references`**: Links `peptide_id` to either `study_id` or `citation_id`.
  - **`peptide_research_indications`**: Links `peptide_id` to specific medical indications and tags them (e.g., most_effective).
  - **`peptide_research_indication_studies`**: Links those indications further down to protocols and studies.

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
When saving this JSON into postgres:
1. Lookup or insert **Dictionaries/Lookups** (`administration_methods`, `benefits`, `side_effects`, `dosages`, `schedules`, `application_places`).
2. Insert **Peptide** (`peptides`).
3. Insert **Peptide Bridges** (`peptide_benefits`, `peptide_side_effects`, `peptide_interactions`).
4. Insert **Protocols** (`peptide_protocols`).
5. Insert **Protocol Bridges & Children** (`protocol_application_places`, `peptide_protocol_reconstitution_steps`, `protocol_quality_indicators`).
6. Insert **Protocol Dosages** (`protocol_dosages`).
7. Insert **Dosage Bridges** (`protocol_dosage_benefits`, `protocol_dosage_side_effects`).


