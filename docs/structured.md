# Structured Database Schema & Insertion Order

This document defines the relational structure and the required insertion order for the `peptides` database to preserve referential integrity.

## 1. Insertion Hierarchy

To maintain foreign key constraints, data must be inserted in the following order:

### Group A: Independent Lookup Tables
These tables have no dependencies on other entities (or only self-reference).
1.  **`categories`**: Peptide categories (supports hierarchical structure via `parent_category_id`).
2.  **`administration_methods`**: Methods of use (Injectable, Oral, etc.).
3.  **`benefits`**: General benefits (Muscle Growth, Recovery, etc.).
4.  **`side_effects`**: Potential side effects.
5.  **`dosages`**: Base dosage units and amounts.
6.  **`schedules`**: Frequency and timing schedules.
7.  **`application_places`**: Body locations for application.
8.  **`research_studies`** / **`citations`**: External references.

### Group B: Core Entities
9.  **`peptides`**: The central record. Depends on `categories` (category_id).

### Group C: Peptide-Specific Relations
These tables link directly to the peptide.
10. **`peptide_benefits`**: Links `peptides` to `benefits`.
11. **`peptide_side_effects`**: Links `peptides` to `side_effects`.
12. **`peptide_interactions`**: Links `peptides` to other peptides (or names).
13. **`peptide_research_indications`**: Specific research categories for a peptide.
14. **`peptide_references`**: Links `peptides` to `research_studies`.

### Group D: Protocol Structure
15. **`peptide_protocols`**: Defines a specific use protocol. Depends on `peptides` and `administration_methods`.

### Group E: Protocol Details
16. **`peptide_protocol_reconstitution_steps`**: Steps to prepare the peptide. Depends on `peptide_protocols`.
17. **`protocol_application_places`**: Junction between `peptide_protocols` and `application_places`.
18. **`protocol_quality_indicators`**: Verification steps. Depends on `peptide_protocols`.
19. **`protocol_dosages`**: The actual dosage plan. Depends on `peptide_protocols`, `dosages`, and `schedules`.

### Group F: Dosage Context
20. **`protocol_dosage_benefits`**: Benefits linked to a specific protocol dose. Depends on `protocol_dosages` and `benefits`.
21. **`protocol_dosage_side_effects`**: Side effects linked to a specific protocol dose. Depends on `protocol_dosages` and `side_effects`.
22. **`peptide_research_indication_studies`**: Links an indication to a study. Depends on `peptide_research_indications` and `research_studies`.

---

## 2. Table Value Relationships & Constraints

| Table Name | Linkage (Foreign Key) | Key Values / Columns |
| :--- | :--- | :--- |
| `peptides` | `category_id` -> `categories(id)` | `name`, `slug`, `overview`, `mechanism_of_action`, `sequence` |
| `peptide_protocols` | `peptide_id`, `administration_method_id` | `name`, `expectations` (JSONB), `best_timing` |
| `peptide_benefits` | `peptide_id`, `benefit_id` | `general_potency`, `general_evidence_level` |
| `peptide_interactions` | `peptide_id_1`, `peptide_id_2` (opt) | `interaction_type` (Enum), `severity`, `description` |
| `protocol_dosages` | `protocol_id`, `dosage_id`, `schedule_id` | `is_default`, `notes`, `sort_order` |
| `protocol_application_places` | `protocol_id`, `application_place_id` | Junction table |

---

## 3. Data Mapping Guidance

*   **Dictionaries**: Before inserting core data, ensure lookup tables (`benefits`, `side_effects`, etc.) are populated or checked for existing names to retrieve IDs.
*   **JSONB Fields**: Columns like `expectations`, `quick_start_guide`, and `pharmacokinetics_json` contain structured nested data.
*   **Enums**: Fields like `interaction_type`, `fda_approval_status`, and `wada_status` use custom types. Values must match the DB definitions.
