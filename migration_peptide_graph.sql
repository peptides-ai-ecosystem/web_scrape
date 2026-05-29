-- Add legend JSONB column to peptide_graph table
-- This stores the marker type to color mapping extracted from the website
-- Example: {"peak": "rgb(34, 197, 94)", "half-life": "rgb(245, 158, 11)"}


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
