---
name: adding-a-scraper
description: Use when web_scrape must read a new kind of site (a new source, not a new competitor target), or when a scraper package under app/scrapers/ gains its own routes or tables. Covers the package, the registry line, the controller and routes, the Alembic revision for owned tables, the test theme and the docs.
---

# Adding a scraper to web_scrape

A new site is a new package in this service, never a new repository or a copy of this one. A new **competitor** for the existing vendor scraper is not a new scraper: add a target through `POST /api/v1/vendors/targets` (or `targets/from-url`) instead.

## Steps
1. **Package** `app/scrapers/<name>/` with the site-specific code only: URL discovery, page extraction, and an `extractors/` folder if there are several. Reuse `app/infrastructure/` for every fetch: `PoliteHttpClient` or `PlaywrightPageFetcher`, `RobotsPolicy`, `HostRateLimiter`, `url_safety.check_url`. No FastAPI import, no SQL.
2. **Registry**: one `ScraperInfo` entry in `app/scrapers/registry.py` (discover, fetch, extract, controller, `writes`, `own_tables`). `tests/ops/test_scraper_registry.py` imports every dotted path in it.
3. **Where rows go**
   - Platform tables (XR-8): a mapper under `app/services/sync/` and repository SQL under `app/repositories/`. Every new platform column is a Drizzle migration in peptides-platform first; follow skill `platform-schema-dependency`.
   - Its own tables: one model file per table in `app/infrastructure/db/models/`, add the table names to `OWN_TABLES`, and an Alembic revision (`uv run alembic revision -m "..."`, version table `alembic_version_web_scrape`). Test it on a throwaway Postgres: `docker run -d --rm -p 55432:5432 -e POSTGRES_PASSWORD=pw postgres:17`, then `DATABASE_URL=postgresql://postgres:pw@127.0.0.1:55432/postgres uv run alembic upgrade head`.
4. **Routes, only if it is a new HTTP feature**: request/response models in `app/models/<name>.py`; a controller in `app/controllers/<name>_controller.py` (it coordinates the scrape and the write); a router in `app/api/v1/endpoints/<name>.py` registered in `app/api/v1/routers.py` (behind the gateway token). Each route is a status mapping plus one call.
5. **Tests**: a folder `tests/<name>/` with `README.md`, a marker registered in `pytest.ini`, fixture pages in the folder, and a row in `tests/README.md`. The suite stays offline.
6. **Docs**: a row in `docs/README.md`; `docs/adding-a-scraper.md` if a step was missing.

## Verify
- `scripts/check.sh` passes; the OpenAPI path list only gained the routes you meant to add.
- `PLATFORM_SCHEMA_REPO=<peptides-platform on staging> uv run pytest tests/sync/test_platform_schema_contract.py -v` passes when the scraper writes platform tables.
- A scheduled run is opt-in per environment (a setting that defaults to off), like `VENDOR_SCRAPE_CRON_ENABLED`.
