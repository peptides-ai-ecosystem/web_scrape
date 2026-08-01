-- Change contraindications and stop_signs columns on peptides table to JSONB
--
-- contraindications: JSON object keyed by week/time period, value is the content.
--   Populated from what_to_expect_{1..n} CSV columns via PeptideMapper.
--   Example: {"Week 1-2": "Minimal noticeable effects", "Week 3-4": "Subtle changes"}
--
-- stop_signs: JSON object keyed by stop-sign number (1..n), value is the statement.
--   Populated from side_effects_and_safety_when_to_stop_{1..n} CSV columns via PeptideMapper.
--   Example: {"1": "Severe headache", "2": "Nausea", "3": "Persistent fatigue"}
--
-- NOTE: Existing TEXT values are NOT auto-converted (PostgreSQL cannot guess
-- how to structure arbitrary text into this shape). Existing data is preserved
-- as JSON strings via the USING cast, so nothing is lost.

-- Change contraindications from TEXT to JSONB
ALTER TABLE peptides
ALTER COLUMN contraindications TYPE JSONB
USING (
    CASE
        WHEN contraindications IS NULL OR contraindications = '' THEN NULL
        ELSE to_jsonb(contraindications::text)
    END
);

-- Change stop_signs from TEXT to JSONB
ALTER TABLE peptides
ALTER COLUMN stop_signs TYPE JSONB
USING (
    CASE
        WHEN stop_signs IS NULL OR stop_signs = '' THEN NULL
        ELSE to_jsonb(stop_signs::text)
    END
);
