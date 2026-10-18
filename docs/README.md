# web_scrape docs

web_scrape hosts two scrapers in one FastAPI service and serves the sync, graph, operations and vendor-pricing API behind the orchestrator gateway at `/web_scrape/*` (callers: the platform admin and the peptide service, XR-14).

## The two scrapers

| Scraper | Reads | Writes | Package | Routes |
|---|---|---|---|---|
| `pep_pedia` | pep-pedia.org peptide pages (Selenium + Chromium) | a CSV, then the **platform's** peptide, relation and `peptide_graph` tables (XR-8, owned by peptides-platform's Drizzle schema) | `app/scrapers/pep_pedia/` | `/api/v1/sync/*`, `/api/v1/evaluation/*`, `/api/v1/core/*`, `/api/v1/csv/*`, graph routes |
| `vendors` | competitor product pages (Playwright, or HTTP for the WooCommerce Store API, Shopify and sitemaps) | **this service's** `vendor_scrape_targets` and `vendor_price_observations` (Alembic, `alembic_version_web_scrape`) | `app/scrapers/vendors/` | `/api/v1/vendors/*`, `/api/v1/scheduler/vendor-scrape/*` |

The registry of scrapers is `app/scrapers/registry.py`. Adding one: `docs/adding-a-scraper.md`.

## The pep-pedia pipeline
1. Discover URLs (`app/scrapers/pep_pedia/crawl_peptide_urls.py`) or take them from the request.
2. Scrape each page into `PeptideData` (`page_scraper.py`, `extractors/`) and write the CSV (`app/infrastructure/csv_storage.py`).
3. Map CSV rows to platform tables in insert order, groups A–F (`app/services/sync/`; insert order, relations and field mapping in `docs/product/sync-schema.md`).
4. Write through `app/repositories/` (all SQL). `PepPediaSyncController` runs steps 1–4 as a background job.
5. Optionally evaluate the result against the CSV (`app/evaluation/`, `/api/v1/evaluation/*`).

## Reference
| Doc | What it covers |
|---|---|
| `product/01-scrape.md` … `04-fastapi-schedule-operations.md` | the pep-pedia scrape, sync, evaluation, API and scheduler in depth |
| `product/05-vendor-scraping.md`, `product/url-only-discovery.md` | the vendor scraper and selector-free discovery |
| `product/sync-schema.md` | mapper insert order, entity relations and CSV column → table column (one document) |
| `adr/` | the decisions, with the file that enforces each |
| `agents/commands.md` | every command (run, test, gate, migrate) |
| `adding-a-scraper.md` | the checklist for a new scraper |
| `archive/graph_analysis.md` | a one-off analysis of the BPC-157 PK graph (archive) |
