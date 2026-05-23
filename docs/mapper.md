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
To maintain referential integrity, inserts must follow this hierarchy (detailed in [structured.md](file:///home/saif/Documents/web_scrape/structured.md)):
1.  **Lookups**: `categories`, `administration_methods`, `benefits`, `side_effects`, `dosages`, `schedules`, `application_places`, `research_studies`.
2.  **Core**: `peptides`.
3.  **Peptide Bridges**: `peptide_benefits`, `peptide_side_effects`, `peptide_interactions`, `peptide_research_indications`, `peptide_references`.
4.  **Protocols**: `peptide_protocols`.
5.  **Protocol Details**: `peptide_protocol_reconstitution_steps`, `protocol_application_places`, `protocol_quality_indicators`, `protocol_dosages`.
6.  **Dosage/Study Context**: `protocol_dosage_benefits`, `protocol_dosage_side_effects`, `peptide_research_indication_studies`.


