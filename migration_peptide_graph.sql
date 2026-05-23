CREATE TABLE IF NOT EXISTS peptide_graph (
    id SERIAL PRIMARY KEY,
    peptide_id INTEGER REFERENCES peptides(id) ON DELETE CASCADE,
    administration_method_id INTEGER REFERENCES administration_methods(id),
    time_range VARCHAR(50),
    peak_concentration VARCHAR(255),
    half_life VARCHAR(255),
    cleared_percentage VARCHAR(255),
    path_data TEXT,
    markers JSONB,
    points JSONB,
    x_axis_labels JSONB,
    y_axis_labels JSONB,
    legend JSONB DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Migrate existing data
INSERT INTO peptide_graph (
    peptide_id, administration_method_id, time_range,
    peak_concentration, half_life, cleared_percentage,
    points, x_axis_labels, y_axis_labels, legend, updated_at
)
SELECT 
    peptide_id, administration_method_id, time_range,
    peak_concentration, half_life, cleared_percentage,
    points, x_axis_labels, y_axis_labels, legend, updated_at
FROM peptide_graph;

-- Drop old table
-- DROP TABLE IF EXISTS peptide_graph;
