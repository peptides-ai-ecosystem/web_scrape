# Architecture (web_scrape)

One FastAPI service (`main.py` -> `app/factory.py`) with three paths and a scheduler. One line per hop; the code is the reference.

## Request path (all routes)
`app/api/gateway_auth.py` checks `X-Gateway-Token` -> `app/api/v1/routers.py` mounts `app/api/v1/endpoints/*` -> a controller (`app/controllers/`, only when a use case coordinates more than one thing) -> `app/services/` -> `app/repositories/` (all SQL) -> `app/infrastructure/` (DB pool, HTTP, browsers). Typed errors from `app/core/errors.py` are mapped to HTTP by `app/api/errors.py`. Request models live in `app/models/`.

## 1. pep-pedia scrape (Selenium + Chromium)
1. `app/scrapers/pep_pedia/crawl_peptide_urls.py` finds peptide URLs, or the request supplies them.
2. `page_scraper.py` + `extractors/` (hero, quick guide, community, section, graph) build a `PeptideData` (`app/core/models.py`).
3. `app/infrastructure/csv_storage.py` writes the CSV.

## 2. Sync into the platform database (XR-8)
1. `app/services/sync/db_import_orchestrator.py` maps each CSV row by group A-F (`group_a/` lookups, `group_b/` peptide, `group_c/` relations, `group_d/` protocols and graph, `group_e/`, `group_f/`); insert order is in `docs/product/sync-schema.md`.
2. `group_sync.py` writes group A and the relations; `graph_import_orchestrator.py` writes `peptide_graph`.
3. Writes go through `app/repositories/` (one file per platform table). Sync is fill-empty-only unless the request says otherwise. `delete_peptide_cascading` in `app/repositories/peptide.py` names every platform table that references a peptide.
4. `app/evaluation/` compares CSV and database after a sync (`/api/v1/evaluation/*`); its reads are `app/repositories/evaluation_repository.py` and `GraphRepository.graph_rows_for_peptide`, so it holds comparison logic only.

## 3. Vendor price scrape (Playwright or plain HTTP)
1. Targets live in `vendor_scrape_targets` (this service's table; `app/repositories/vendor_target.py`), with `config/vendor_targets.example.json` as the shape of an optional file seed.
2. `app/services/vendor_scrape_runner.py` wires `app/scrapers/vendors/vendor_scraper.py`: robots, per-host rate limit, fetch, extract, score, delta review, persist.
3. Selector-free targets use `url_discovery.py` (Woo Store API, Shopify, sitemaps, JSON-LD); `extractors/` parse pages.
4. Observations are append-only in `vendor_price_observations`; the platform reads `observations/accepted-latest`. `vendor_products_publisher.py` is an unimplemented seam (an XR-14 follow-up).

## Scheduler and jobs
`app/core/scheduler.py` (APScheduler) runs the pep-pedia sync and the optional vendor cron; `app/core/job_queue.py` tracks background jobs for the polling endpoints. One scheduler per database: staging pins `START_SCHEDULER=false`.

## Where things are registered
`app/scrapers/registry.py` lists the scrapers; `app/core/config.py` is the only settings module; `alembic/` covers `vendor_scrape_targets` and `vendor_price_observations` only.
