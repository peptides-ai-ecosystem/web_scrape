# Peptide Database & Visualization Pipeline Guide

This document provides a step-by-step guide to setting up and running the peptide scraping, database synchronization, and graph visualization pipeline.

## Prerequisites
- **Git**: For cloning the repository.
- **Python**: With the `uv` package manager installed.
- **PostgreSQL**: Either via Docker (Recommended) or a Local installation.

---

## Step 1: Clone the Repository
Begin by cloning the codebase to your local machine and navigating into the project directory:
```bash
git clone https://github.com/sazzad1779-dev/web_scrape.git
cd web_scrape
```

---

## Step 2: Database Setup
You can set up the database using either **Docker (Recommended)** or a **Local PostgreSQL Installation**. Please follow the instructions for your preferred method.









### setup the cloud supabase

1. **Dump sql from original db**
2. **restore in mock supabase db**
```bash
docker run --rm -i postgres:17 psql "postgresql://postgres.kyfvfzivwzetdilgjmrk:49yRlw2E0RmloZsL@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres" < full_dump.sql
```

3. **Create peptide-graph table**
```bash
docker run --rm -i postgres:17 psql "postgresql://postgres.kyfvfzivwzetdilgjmrk:49yRlw2E0RmloZsL@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres" < migration_peptide_graph.sql
```

### Option A: Docker Setup (Recommended)
1. **Start the PostgreSQL service** (in the background):
   ```bash
   docker compose up -d postgres
   ```
2. **Restore the initial database** from the dump file:
   ```bash
   docker exec -i postgres-container psql -U admin -d peptides < full_dump.sql  
   ```
3. **Apply the graph table migration**:
   ```bash
   docker exec -i postgres-container psql -U admin -d peptides < migration_peptide_graph.sql
   ```

*(Optional)* Useful Docker PostgreSQL commands:
- **Access DB shell**: `docker exec -it postgres-container psql -U admin -d peptides`
- **List databases**: `\l`
- **List tables**: `\dt`
- **Exit shell**: `\q`

### Option B: Local PostgreSQL Setup (Fedora/Linux)
1. **Start the PostgreSQL service**:
   ```bash
   sudo systemctl start postgresql
   ```
2. **Create the `peptides` database** (as the postgres user):
   ```bash
   sudo -i -u postgres psql -c "CREATE DATABASE peptides;"
   ```
3. **Restore the initial database** from the dump file:
   ```bash
   psql -U postgres -d peptides < full_dump.sql
   ```
4. **Apply the graph table migration**:
   ```bash
   psql -U postgres -d peptides < migration_peptide_graph.sql
   ```

*(Optional)* Useful Local PostgreSQL commands:
- **Check service status**: `systemctl status postgresql`
- **Enter Postgres user shell**: `sudo -i -u postgres`
- **Connect to DB**: `psql -d peptides`

---

## Step 3: Local Environment Setup
Install all required Python dependencies into a virtual environment using `uv`:
```bash
uv sync
```

---

## Step 4: Run the Ingestion Pipeline
The `main.py` script is responsible for scraping data from the website and synchronizing it with your local PostgreSQL database. Choose the command that fits your needs:

- **Run Full Pipeline (Scrape & Sync):**
  ```bash
  uv run main.py --scrape --sync
  ```
- **Only Scrape Data (Saves to CSV):**
  ```bash
  uv run main.py --scrape
  ```
- **Only Sync Data (From CSV to Database):**
  ```bash
  uv run main.py --sync
  ```

---

## Step 5: Start the Visualization Dashboard
Launch the FastAPI backend server to serve the graph data and the visualization interface:
```bash
uv run -m viz_server
```
Once the server is running, open your web browser and navigate to:
- **Visualization Interface**: [http://localhost:5000/visualization/](http://localhost:5000/visualization/)
- **API Root**: [http://localhost:5000/](http://localhost:5000/)

---
---

## Technical Appendix: Visualization Mechanism
The visualization system converts raw extracted graph data into interactive SVG charts using a "direct-path injection" approach.

### Workflow: Data to Pixels
1. **Data Extraction**: The scraper identifies SVG paths and coordinate markers on the original website.
2. **Database Storage**: Instead of just raw points, we store the actual SVG `path_data` string and JSON-formatted markers (`markers`, `points`, `x_axis_labels`).
3. **API Delivery**: The FastAPI backend fetches this record and serves it as a JSON object.
4. **Frontend Rendering**: The `src/visualization/script.js` and `src/visualization/index.html` use a fixed coordinate system (ViewBox `0 0 100 45`) to render the graph.

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
