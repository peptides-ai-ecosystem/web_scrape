# Pep-Pedia Web Scraper & Visualization Pipeline

A robust, modular web scraper designed to extract comprehensive peptide data and graph coordinates from [pep-pedia.org](https://pep-pedia.org). Built with Python, Selenium, PostgreSQL, and FastAPI, it supports concurrent scraping, structured data export, database synchronization, and interactive visualization.

## 🚀 Features

- **Deep Extraction**: Captures Hero sections, Quick Guides, and multiple content sections including accordions.
- **Graph Data Capture**: Extracts complex SVG paths and coordinate markers for graph rendering.
- **Concurrent Processing**: Utilizes multiprocessing to scrape multiple peptide URLs simultaneously.
- **Auto-Discovery**: Automatically crawls the bridge page to find all available peptide links.
- **Database Synchronization**: Built-in scripts to map and sync scraped CSV data into a PostgreSQL database.
- **Interactive Dashboard**: A FastAPI-powered backend and frontend dashboard to visualize the extracted peptide data and SVG graphs.
- **Docker Ready**: Supports running in a fully containerized ecosystem via Docker Compose.

---

## 📖 Execution Guide

**For comprehensive, step-by-step instructions on setting up the database, running the web scraper, and launching the visualization server, please read the [Execution Guide](execution_guide.md).**

The Execution Guide contains details for both **Docker (Recommended)** and **Local PostgreSQL** setup paths.

---

## 🛠️ Quick Start Summary

This is a brief summary of how to get started. See the [Execution Guide](execution_guide.md) for full commands and database setup.

### 1. Setup Environment
Ensure you have `uv` installed. If not, install it via:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone & Install
```bash
git clone https://github.com/sazzad1779-dev/web_scrape.git
cd web_scrape
uv sync
```

### 3. Run the Pipeline (`main.py`)
The `main.py` script orchestrates the pipeline:
```bash
uv run main.py --scrape --sync
```
*(You can also run `--scrape` or `--sync` individually.)*

### 4. Launch the Visualization Dashboard
```bash
uv run -m viz_server
```
Then navigate to `http://localhost:5000/visualization/` in your browser.

---

## 🏗️ Code Architecture

The project follows a modular design for maintainability and scalability:

- **`main.py`**: The entry point. Handles URL discovery and orchestrates the scraping and database synchronization process.
- **`viz_server.py`**: The FastAPI server that delivers database graph records and hosts the frontend UI.
- **`src/core/`**: Defines data models (`Peptide`, `HeroSection`, `Graph`, etc.) and interfaces.
- **`src/extractors/`**: Specialized classes for parsing specific parts of the page (Hero, Quick Guide, Content Sections, Graphs).
- **`src/infrastructure/`**: Handles external concerns like `WebDriver` creation, `CSV` storage, and `PostgreSQL` database connections.
- **`src/services/`**: High-level orchestrators (`PageScraper`, `ScraperManager`) that combine extractors and infrastructure.
- **`src/visualization/`**: Frontend HTML/JS/CSS for dynamically rendering the extracted SVG graph data.
- **`src/config.py`**: Centralized configuration for timeouts, paths, crawling logic, and credentials.
