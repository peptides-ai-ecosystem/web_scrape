# Peptide Database & Visualization Pipeline Guide

This document explains the end-to-end execution flow of the peptide scraping, database synchronization, and graph visualization system.

## 1. Execution Pipeline

The pipeline is divided into four main stages: Database Setup, Environment Preparation, Data Ingestion, and Visualization.

### Step 1: Database Initialization
1.  **Dump existing data**: Ensure you have the latest `full_dump.sql` from the production/existing database.
    ```powershell
    # Example command to dump (if applicable)
    pg_dump -h <host> -U <user> <db_name> > full_dump.sql
    ```
2.  **Restore to local**: Restore the dump into your local PostgreSQL instance.
    ```powershell
    psql -h localhost -U postgres -d peptide_db -f full_dump.sql
    ```
3.  **Apply Migrations**: Create the necessary table for storing graph data.
    ```powershell
    psql -h localhost -U postgres -d peptide_db -f migration_peptide_graph.sql
    ```

### Step 2: Local Environment Setup
Install the required Python dependencies in your virtual environment:
```powershell
pip install -r requirements.txt
```

### Step 3: Run the Ingestion Pipeline
The `main.py` script handles both scraping and database synchronization.
*   **Full Run (Scrape + Sync)**:
    ```powershell
    python main.py --scrape --sync --limit 100
    ```
    *   `--scrape`: Crawls URLs and extracts peptide data into a CSV.
    *   `--sync`: Takes the CSV data and maps/inserts it into the PostgreSQL tables.

### Step 4: Start Visualization API
Launch the FastAPI server to serve the graph data and the visualization frontend.
```powershell
python viz_server.py
```
Open your browser at: `http://localhost:5000/` or directly to the dashboard at `http://localhost:5000/visualization/`

---

## 2. Visualization Mechanism

The visualization system converts raw extracted graph data into interactive SVG charts using a "direct-path injection" approach.

### Workflow: Data to Pixels
1.  **Data Extraction**: The scraper identifies SVG paths and coordinate markers on the original website.
2.  **Database Storage**: Instead of just raw points, we store the actual SVG `path_data` string and JSON-formatted markers (`markers`, `points`, `x_axis_labels`).
3.  **API Delivery**: The FastAPI backend fetches this record and serves it as a JSON object.
4.  **Frontend Rendering**: The [src/visualization/script.js](src/visualization/script.js) and [src/visualization/index.html](src/visualization/index.html) use a fixed coordinate system (ViewBox `0 0 100 45`) to render the graph.

### Core Implementation Logic

#### SVG Path Injection
The frontend receives the `path_data` string (e.g., `M10,35 C12,30 ...`) and directly sets it as the `d` attribute of the SVG path.

```javascript
// From src/visualization/script.js
// Update the main curve
graphPath.setAttribute('d', data.path_data);

// Create the area fill by closing the path to the baseline
if (graphFill && data.path_data) {
    // Appends: Line to bottom-right, Line to bottom-left, Close path
    graphFill.setAttribute('d', `${data.path_data} L ${SVG_X_MAX} ${SVG_Y_BOTTOM} L ${SVG_X_MIN} ${SVG_Y_BOTTOM} Z`);
}
```

#### Marker Mapping
Markers are stored as JSONB in the database. The JS code iterates through these coordinates and places SVG `<circle>` or `<text>` elements on the `markers-layer`.

```javascript
// Simplified marker rendering logic
data.markers.forEach(marker => {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', marker.x);
    circle.setAttribute('cy', marker.y);
    circle.setAttribute('r', '0.8');
    markersLayer.appendChild(circle);
});
```

### Key Visualization Features
- **Dynamic Tab Switching**: Allows users to toggle between `24h`, `7d`, `14d`, and `30d` views instantly by fetching different rows from `peptide_graph`.
- **Responsive Viewbox**: Uses `preserveAspectRatio="xMidYMid meet"` to ensure the graph looks consistent across different screen sizes while maintaining the internal coordinate system.
- **Gradient Fills**: Uses SVG `<defs>` to apply a smooth blue gradient to the area under the curve for a modern "dashboard" look.
