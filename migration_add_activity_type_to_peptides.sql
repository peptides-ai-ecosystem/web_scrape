-- Add activity_type column to peptides table
-- Values: NULL (default, when inserted via app), 'automatic', 'manual'
-- Similar to action_type in peptide_graph table but nullable

ALTER TABLE peptides
ADD COLUMN IF NOT EXISTS activity_type VARCHAR(20) DEFAULT NULL
CHECK (activity_type IS NULL OR activity_type IN ('automatic', 'manual'));

-- Add index for filtering by activity_type
CREATE INDEX IF NOT EXISTS idx_peptides_activity_type ON peptides (activity_type);
