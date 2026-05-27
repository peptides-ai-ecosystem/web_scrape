# Pep-Pedia Web Scraper

A robust, modular web scraper designed to extract comprehensive peptide data from [pep-pedia.org](https://pep-pedia.org). Built with Python, Selenium, and Docker, it supports concurrent scraping and structured data export.

## 🚀 Features

- **Deep Extraction**: Captures Hero sections, Quick Guides, and multiple content sections including accordions.
- **Concurrent Processing**: Utilizes multiprocessing to scrape multiple peptide URLs simultaneously.
- **Modular Architecture**: Clean separation of concerns between core models, extractors, and infrastructure.
- **Dockerized**: Ready-to-run containerized environment with all system dependencies pre-configured.
- **Auto-Discovery**: Automatically crawls the bridge page to find all available peptide links.
- **Robust Storage**: Exports results to a master CSV file with error logging for failed pages.

---

## 🛠️ Prerequisites

- **Python**: 3.12+
- **Browser**: Google Chrome / Chromium
- **Tools**: `uv` (modern Python package manager)
- **Containerization**: Docker & Docker Compose (optional, for containerized runs)

---

## 💻 Local Installation & Usage

### 1. Setup Environment
Ensure you have `uv` installed. If not, install it via:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone & Install
```bash
git clone <repo-url>
cd web_scrape
uv sync
```

### 3. Run the Scraper
Start the full scraping workflow (discovery + extraction):
```bash
uv run python main.py
```
Data will be saved to `output_v6/pep_pedia_master.csv`.

---

## 🐳 Docker Usage

Run the scraper without worrying about local Chrome/ChromeDriver versions.

### Build and Run
```bash
docker compose build
docker compose up
```

The `output_v6` directory is mounted as a volume, so your scraped data and error logs will persist on your host machine.

---

## 🏗️ Code Architecture

The project follows a modular design for maintainability and scalability:

- **`main.py`**: The entry point. Handles URL discovery and orchestrates the scraping process.
- **`src/core/`**: Defines data models (`Peptide`, `HeroSection`, etc.) and interfaces.
- **`src/extractors/`**: Specialized classes for parsing specific parts of the page (Hero, Quick Guide, Content Sections).
- **`src/infrastructure/`**: Handles external concerns like `WebDriver` creation and `CSV` storage.
- **`src/services/`**: High-level orchestrators (`PageScraper`, `ScraperManager`) that combine extractors and infrastructure.
- **`src/config.py`**: Centralized configuration for timeouts, paths, and crawling logic.

---

## 🔄 Full Workflow

1. **Discovery**: `crawl_peptide_urls()` in `config.py` visits the browse page and collects all peptide links.
2. **Orchestration**: `ScraperManager` receives the URLs and distributes them across multiple processes.
3. **Scraping**: `PageScraper` navigates to each URL and uses multiple `Extractors` to parse the DOM.
4. **Storage**: `CSVStorage` converts the unstructured data into a tabular format and appends it to the master CSV.
5. **Logging**: Any failures are captured and written to `error_log.txt` for later review.

---

## ⚙️ Configuration

Key settings can be adjusted in `src/config.py`:
- `TIMEOUT`: Page load and element wait timeouts.
- `OUTPUT_DIR`: Directory for CSV and logs.
- `button_skip_list`: List of keywords to filter out irrelevant UI elements during scraping.

