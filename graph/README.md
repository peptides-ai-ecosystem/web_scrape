# Peptide Graph Scraper & Visualizer

This directory contains tools for scraping dynamic pharmacokinetics graph data from pep-pedia.org and visualizing it in a premium, interactive web dashboard.

## Features
- **Dynamic Scraper**: Extracts SVG path data, markers (Peak, Half-life), summary stats, and axis labels across multiple time ranges (24h, 7d, 14d, 30d).
- **Interactive Dashboard**: A premium UI that allows switching between time ranges with smooth transitions and real-time data updates.
- **Hover Tooltip**: Hover over the graph line to see precise `time : percentage%` values at any point on the curve.
- **Data Persistence**: Saves all extracted data into a structured JSON format.

## Directory Structure
- `scraper.py`: Selenium-based scraper for extracting dynamic SVG data.
- `graph_data.json`: The primary data store for the visualization.
- `visualization/`: Web dashboard implementation.
    - `index.html`: Main dashboard structure.
    - `styles.css`: Premium aesthetics and layout.
    - `script.js`: Interactivity and SVG rendering logic.
- `visualizer.py`: A Python-based static visualizer using Matplotlib.

## Getting Started

### 1. Scrape Data
Run the scraper for your target peptide. By default, it scrapes "Dihexa" if no URL is provided.

```bash
# Basic usage
python3 graph/scraper.py

# Scrape a specific peptide
python3 graph/scraper.py https://pep-pedia.org/peptides/BPC-157
```

### 2. Launch the Visualization
The dashboard requires a local server to load the JSON data correctly due to browser security (CORS) rules.

```bash
# Start a simple server from the project root
python3 -m http.server 8000
```

Open your browser and navigate to:
**[http://localhost:8000/graph/visualization/index.html](http://localhost:8000/graph/visualization/index.html)**


```bash
## to stop the server
kill $(pgrep -f "python3 -m http.server 8000")
```



### 3. Dynamic Updates
To visualize a different peptide, just run the `scraper.py` again with the new URL and refresh the browser page. The dashboard will automatically update with the new data.

---
*Created by Antigravity*
