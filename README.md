# 🧬 Pep-Pedia — Web Scraper & Visualization Pipeline

> **Extract** → **Sync** → **Evaluate** → **Visualize** — An end-to-end pipeline for scraping peptide pharmacokinetics data from [pep-pedia.org](https://pep-pedia.org), synchronizing it to PostgreSQL, evaluating sync quality, and serving interactive graph visualizations via a FastAPI dashboard.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Selenium](https://img.shields.io/badge/Selenium-4.40-43B02A?style=flat&logo=selenium&logoColor=white)](https://selenium.dev)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)

---

## 📑 Feature Documentation

Each feature is documented in detail with business logic, architecture diagrams, and code workflows:

| # | Feature | Document | Key Modules |
|---|---------|----------|-------------|
| 1 | **🕷️ Web Scrape** | [`docs/features/01-scrape.md`](docs/features/01-scrape.md) | `PageScraper`, `ScraperManager`, extractors, `WebDriverFactory`, `CSVStorage` |
| 2 | **🔄 Database Sync** | [`docs/features/02-sync.md`](docs/features/02-sync.md) | `DbImportOrchestrator`, `GraphImportOrchestrator`, mappers (groups A–F) |
| 3 | **📊 Evaluation** | [`docs/features/03-evaluation.md`](docs/features/03-evaluation.md) | `EvaluationEngine`, `CsvExpectationBuilder`, `DbActualFetcher`, `GraphEvaluator` |
| 4 | **🚀 FastAPI & Scheduler & Operations** | [`docs/features/04-fastapi-schedule-operations.md`](docs/features/04-fastapi-schedule-operations.md) | `api_server.py`, APScheduler, `JobQueue`, async endpoints, visualization |

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Installation |
|------|---------|-------------|
| `uv` | ≥ 0.x | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker (recommended) | ≥ 24.x | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| Or: PostgreSQL | 17.x | Local install via system package manager |

### 1. Clone & Install

```bash
git clone https://github.com/sazzad1779-dev/web_scrape.git
cd web_scrape
uv sync
```

### 2. Configure Environment

```bash
# Copy the environment template
cp .env.example .env   # (create one if none exists)

# Set your database URL
DATABASE_URL=postgresql://user:password@localhost:5432/peptides_db
OUTPUT_DIR="output_dir"
LOG_DIR="log"
TIMEOUT=10
```

### 3. Database Setup

**Option A — Docker (recommended):**

```bash
# Start PostgreSQL
docker compose up -d postgres

# Restore initial schema + data
docker exec -i postgres-container psql -U admin -d peptides < full_dump_main.sql

# Apply graph table migration
docker exec -i postgres-container psql -U admin -d peptides < migration_peptide_graph.sql
```

**Option B — Local PostgreSQL:**

```bash
# Create database
sudo -i -u postgres psql -c "CREATE DATABASE peptides;"

# Restore data
psql -U postgres -d peptides < full_dump_main.sql
psql -U postgres -d peptides < migration_peptide_graph.sql
```

> **💡 Detailed database guide**: See [`execution_guide.md`](execution_guide.md) for both Docker and local setup steps.

### 4. Run — Choose Your Path

The project provides **two entry points** depending on your use case:

---

#### 🧪 Path A: CLI Pipeline (`main.py`) — For Ad-Hoc Operations

Use `main.py` when you need to run one-off scraping, syncing, or evaluation from the command line.

```bash
# ── Full pipeline: scrape → sync ──
uv run main.py --scrape --sync

# ── Scrape only (saves to CSV, no DB) ──
uv run main.py --scrape

# ── Sync only (reads existing CSV → DB) ──
uv run main.py --sync

# ── Evaluate sync quality ──
uv run main.py --evaluate

# ── With limits (for testing) ──
uv run main.py --scrape --sync --limit 5

# ── Specific URLs (skip auto-discovery) ──
uv run main.py --scrape --url https://pep-pedia.org/peptides/example

# ── Evaluate + save JSON report ──
uv run main.py --evaluate --eval-output output/eval_report.json

# ── Delete a peptide from DB ──
uv run main.py --delete some-peptide-slug
```

| Flag | Description |
|------|-------------|
| `--scrape` | Extract data from pep-pedia.org → saves to `output/pep_pedia_master.csv` |
| `--sync` | Sync CSV data to PostgreSQL (core tables) |
| `--evaluate` | Compare CSV expectations vs DB actuals (13 checks/peptide) |
| `--eval-output PATH` | Save evaluation JSON report |
| `--url URL [URL ...]` | Scrape specific URLs (skips crawling) |
| `--limit N` | Process at most N peptides |
| `--delete SLUG` | Delete a peptide from DB |

---

#### 🌐 Path B: API Server (`api_server.py`) — For Production & Dashboard

Use `api_server.py` when you need the HTTP API, automated scheduling, job tracking, and the web visualization dashboard.

```bash
# Start the consolidated API server
uv run api_server.py

# Server starts at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

**What the server provides:**

| Area | Endpoints / Features |
|------|---------------------|
| **Sync API** | `POST /api/v1/sync/core` — scrape + core DB sync |
| | `POST /api/v1/sync/graph` — scrape + graph DB sync |
| | `POST /api/v1/sync/graph-missing` — sync only missing graph data |
| **Evaluation API** | `POST /api/v1/evaluation/core` — 13 checks per peptide |
| | `POST /api/v1/evaluation/graph` — 5 graph-specific checks |
| **Graph API** | `GET /api/v1/graph/peptides` — list peptides with graph data |
| | `GET /api/v1/graph/peptide/{id}/methods` — methods for a peptide |
| | `GET /api/v1/graph/graph/{id}?method=` — graph coordinates & SVG paths |
| **Operations** | `GET /api/v1/operations/jobs` — list all jobs |
| | `GET /api/v1/operations/job/{id}` — track job progress |
| | `DELETE /api/v1/operations/job/{id}` — cancel a running job |
| | `GET /api/v1/operations/health` — system health & stats |
| **Scheduler** | Automated sync every 12 hours (configurable) |
| **Dashboard** | `/visualization/` — interactive graph viewer |
| **Swagger UI** | `/docs` — auto-generated API explorer |

---

## 🤔 `main.py` vs `api_server.py` — Which One Should I Use?

| Criterion | `main.py` (CLI) | `api_server.py` (API Server) |
|-----------|-----------------|------------------------------|
| **Best for** | One-off scraping, testing, debugging | Production, automation, integration |
| **Interface** | Command-line with argparse | REST API + Swagger UI |
| **Async jobs** | ❌ No — runs synchronously | ✅ Yes — background tasks with job queue |
| **Scheduling** | ❌ Manual only | ✅ APScheduler (configurable interval) |
| **Job tracking** | ❌ Not applicable | ✅ In-memory job queue, cancellable |
| **Visualization** | ❌ No | ✅ Interactive dashboard at `/visualization/` |
| **Graph API** | ❌ No | ✅ Full graph data endpoints |
| **When to use** | "I want to scrape 5 peptides and check the CSV" | "I need to run this in production and monitor results" |

**Recommendation**: **Keep both.** Use `main.py` for development, testing, and one-off tasks. Use `api_server.py` for production deployment and when you need the dashboard. The `api_server.py` can also trigger all the same operations via its API endpoints — no feature is lost by moving to the server.

---

## 🏗️ Project Architecture

```mermaid
graph TB
    subgraph External["External"]
        A[pep-pedia.org]
    end

    subgraph CLI["CLI Layer"]
        B[main.py]
    end

    subgraph API["API Layer"]
        C[api_server.py<br/>FastAPI]
        D[Scheduler<br/>APScheduler]
        E[JobQueue<br/>In-memory]
    end

    subgraph Core["Core Pipeline"]
        F[ScraperManager]
        G[PageScraper + Extractors]
        H[CSVStorage]
        I[DbImportOrchestrator]
        J[GraphImportOrchestrator]
        K[Evaluation Engine]
    end

    subgraph Storage["Storage Layer"]
        L[(PostgreSQL)]
        M[output/pep_pedia_master.csv]
    end

    subgraph Frontend["Frontend"]
        N[Visualization Dashboard<br/>HTML/JS/SVG]
    end

    A --> G
    B --> F
    C --> E
    C --> D
    D --> F
    E --> F & I & J & K
    F --> G
    G --> H
    H --> M
    M --> I
    M --> J
    M --> K
    I --> L
    J --> L
    K --> L
    C --> N
    N --> L
```

### Directory Structure

```
├── api_server.py              # 🚀 FastAPI server (sync API, evaluation, graph, dashboard)
├── main.py                    # 🧪 CLI entry point (scrape, sync, evaluate, delete)
├── viz_server.py              # 📊 Legacy visualization-only server
│
├── docs/
│   ├── features/
│   │   ├── 01-scrape.md           # 🕷️ Scrape feature deep-dive
│   │   ├── 02-sync.md             # 🔄 Sync feature deep-dive
│   │   ├── 03-evaluation.md       # 📊 Evaluation feature deep-dive
│   │   └── 04-fastapi-schedule-operations.md  # 🚀 API & Operations deep-dive
│   ├── graph_analysis.md
│   ├── mapper.md
│   ├── mapping_analysis.md
│   ├── structure_data.md
│   └── structured.md
│
├── src/
│   ├── core/                   # Data models, interfaces, job queue, scheduler
│   │   ├── models.py           #   PeptideData, GraphData, HeroData, etc.
│   │   ├── interfaces.py       #   IExtractor, IStorage, IScraper
│   │   ├── job_queue.py        #   In-memory job queue (Job, JobStatus, JobQueue)
│   │   └── scheduler.py        #   APScheduler integration
│   │
│   ├── extractors/             # 🕷️ Specialized page section parsers
│   │   ├── base.py             #   BaseExtractor (safe_click, wait_for_loading)
│   │   ├── hero.py             #   HeroExtractor — name, subtitle, facts
│   │   ├── quick_guide.py      #   QuickGuideExtractor — dosage, timing
│   │   ├── community.py        #   CommunityExtractor — insights, polls
│   │   ├── section.py          #   SectionExtractor — accordions, tabs, tables, lists
│   │   └── graph.py            #   GraphExtractor — SVG paths, markers, axis labels
│   │
│   ├── services/               # Orchestration layer
│   │   ├── scraper_manager.py  #   Multiprocessing pool of PageScrapers
│   │   └── page_scraper.py     #   Single URL scraper (category loop + all extractors)
│   │
│   ├── mappers/                # 🔄 CSV → structured DB payloads
│   │   ├── db_import_orchestrator.py    # Core table sync orchestrator
│   │   ├── graph_import_orchestrator.py # Graph table sync orchestrator
│   │   ├── group_a/            #   Lookup mappers (benefits, side-effects, dosages...)
│   │   ├── group_b/            #   Peptide mapper
│   │   ├── group_c/            #   Relation mappers (interactions, indications)
│   │   ├── group_d/            #   Protocol & Graph mappers
│   │   ├── group_e/            #   (Additional groups)
│   │   └── group_f/            #
│   │
│   ├── evaluation/             # 📊 Sync quality evaluation
│   │   ├── runner.py           #   Orchestrator: CSV → build → fetch → compare → report
│   │   ├── csv_expectation_builder.py # Derive expected DB state from CSV
│   │   ├── db_actual_fetcher.py       # Query actual DB state (10 queries/peptide)
│   │   ├── evaluation_engine.py       # 13 core checks + result dataclasses
│   │   ├── graph_evaluator.py         # 5 graph-specific checks
│   │   └── reporter.py                # Console + JSON output
│   │
│   ├── infrastructure/         # External services
│   │   ├── webdriver_factory.py #   Selenium Chrome driver (headless, anti-detection)
│   │   ├── csv_storage.py      #   CSV read/write (pandas DataFrame)
│   │   └── db/                 #   PostgreSQL: connection pool, repositories (peptide, graph, lookup...)
│   │
│   ├── api/                    # 🌐 FastAPI routes
│   │   └── v1/
│   │       ├── routers.py      #   Router aggregation
│   │       └── endpoints/
│   │           ├── sync.py     #   POST /sync/* — scrape + DB sync
│   │           ├── evaluation.py  # POST /evaluation/* — run evaluations
│   │           ├── graph.py    #   GET /graph/* — graph data API
│   │           └── operations.py # GET /operations/* — job tracking, health
│   │
│   ├── utils/
│   │   ├── crawl_peptide_urls.py  # Auto-discover peptide URLs via Selenium
│   │   ├── peptide_utils.py       # Slug normalization, matching
│   │   └── error_tracker.py       # Error collection & reporting
│   │
│   ├── visualization/         # Frontend dashboard
│   │   ├── index.html         #   Graph viewer UI
│   │   ├── script.js          #   SVG rendering engine
│   │   └── styles.css         #   Styling
│   │
│   └── config.py              # Centralized config (paths, timeouts, env vars)
│
├── requirements.txt
├── pyproject.toml
├── Dockerfile                 # 🐳 Python + Chromium Docker image
├── docker-compose.yml         # PostgreSQL + scraper services
├── full_dump_main.sql         # Initial database dump
├── migration_peptide_graph.sql # Graph table migration
└── sync_supabase.sh           # DB migration helper script
```

---

## 🔄 Data Flow Overview

```mermaid
flowchart LR
    Web["pep-pedia.org"] -->|Scrape| CSV["output/pep_pedia_master.csv"]
    CSV -->|Sync| DB[("PostgreSQL<br/>Core Tables")]
    CSV -->|Sync| GraphDB[("PostgreSQL<br/>Graph Tables")]
    DB -->|Evaluate| Report["Evaluation Report"]
    GraphDB -->|Evaluate| GraphReport["Graph Eval Report"]
    DB -->|API| Dashboard["Visualization Dashboard"]
    GraphDB -->|API| Dashboard

    style Web fill:#f9f,stroke:#333
    style CSV fill:#ff9,stroke:#333
    style DB fill:#9cf,stroke:#333
    style Dashboard fill:#9f9,stroke:#333
```

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Specific test modules
uv run pytest src/tests/test_graph_extractor.py -v
uv run pytest src/tests/test_mapping_groups.py -v
```

---

## 🐳 Docker Deployment

```bash
# Build and run all services
docker compose up --build

# This starts:
#   - PostgreSQL 17 on port 15432
#   - Scraper service with Chromium (2GB shared memory)
```

---

## 📚 Additional Documentation

| Document | Description |
|----------|-------------|
| [`execution_guide.md`](execution_guide.md) | Step-by-step database setup (Docker + local) |

---

*Built with Python, Selenium, FastAPI, PostgreSQL, and ❤️*
