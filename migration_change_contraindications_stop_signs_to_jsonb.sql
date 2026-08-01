-- Change contraindications and stop_signs columns on peptides table to JSONB
--
-- contraindications: JSON object keyed by week/week range, value is the content.
--   Example: {"1-2": "Do not use with NSAIDs", "3": "Monitor blood pressure"}
--
-- stop_signs: JSON array of stop-sign indicators.
--   Example: ["Severe headache", "Nausea", "Persistent fatigue"]
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
