-- Add legend JSONB column to peptide_graph table
-- This stores the marker type to color mapping extracted from the website
-- Example: {"peak": "rgb(34, 197, 94)", "half-life": "rgb(245, 158, 11)"}

ALTER TABLE peptide_graph
ADD COLUMN IF NOT EXISTS legend JSONB DEFAULT NULL;

-- Create index for efficient queries
CREATE INDEX IF NOT EXISTS idx_peptide_graph_legend ON peptide_graph USING gin(legend);
