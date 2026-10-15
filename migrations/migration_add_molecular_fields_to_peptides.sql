-- Add molecular_type, molecular_length, molecular_weight columns to peptides table
-- These store raw values scraped from pep-pedia (e.g. 'Modified ACTH analog',
-- '7 amino acids', '1,007.16 Da') so VARCHAR is needed.

ALTER TABLE peptides
ADD COLUMN IF NOT EXISTS molecular_type VARCHAR(100) DEFAULT NULL;

ALTER TABLE peptides
ADD COLUMN IF NOT EXISTS molecular_length VARCHAR(100) DEFAULT NULL;

ALTER TABLE peptides
ADD COLUMN IF NOT EXISTS molecular_weight VARCHAR(100) DEFAULT NULL;

-- Add indexes for potential filtering/sorting
CREATE INDEX IF NOT EXISTS idx_peptides_molecular_type ON peptides (molecular_type);
CREATE INDEX IF NOT EXISTS idx_peptides_molecular_weight ON peptides (molecular_weight);
