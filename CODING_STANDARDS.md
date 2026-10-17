Shared Python rules (layering, settings, migrations on a shared database, logging): [`orchestrator/docs/ecosystem/CODING_STANDARDS.python.md`](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/CODING_STANDARDS.python.md). This file adds the web_scrape rules. Rules only; the code is the reference for how.

# Coding standards — web_scrape

## Done means
- `scripts/check.sh` passes and the change has a test in the matching `tests/<theme>/` folder (`tests/README.md` lists the themes).
- The doc that describes the changed behaviour is updated in the same change. Tracker labels and status notes go to the tracker, not the docs.
- The OpenAPI path list is unchanged unless the change is meant to add or change a route; the platform admin and peptide call these paths through the gateway at `/web_scrape` (XR-14).

## Layering
- `app/api/v1/endpoints/` → `app/controllers/` → `app/services/` → `app/repositories/` → `app/infrastructure/`.
- A route function is a status mapping plus one call downward. Request and response models live in `app/models/<feature>.py`, not in the endpoint file.
- A controller exists only when the use case coordinates more than one thing (a scrape plus a write: `PepPediaSyncController`, `VendorScrapeController`). A controller method that only does `return some_service.foo()` is deleted; the endpoint calls the service.
- Services, controllers, scrapers and repositories never import FastAPI. They raise the typed errors in `app/core/errors.py`; the endpoint maps them with `app/api/errors.py` (same status, same `detail`).
- All SQL lives in `app/repositories/`, one file per table (or per read model such as `peptide_inspector.py`). No SQL in endpoints, services, controllers or scrapers.
- Background work receives a `schedule` callable (`BackgroundTasks.add_task` from the endpoint); it does not take FastAPI objects.

## Scrapers
- A scraper is one package under `app/scrapers/` plus one line in `app/scrapers/registry.py`. It does not import FastAPI and does not write SQL. Checklist: `docs/adding-a-scraper.md`.
- Every request to a site we do not own goes through `app/infrastructure/`: `PoliteHttpClient` or `PlaywrightPageFetcher`, `RobotsPolicy`, `HostRateLimiter` and the SSRF guard `url_safety.check_url`. Never add a second HTTP client or retry loop.
- A blocked host, a robots.txt disallow or a 403 is recorded as an observation status and left alone. Never rotate user agents, proxies or headers to get past it.
- Our own stores (`OWNED_STORE_DOMAINS` / `OWNED_STORE_VENDORS`) are never competitor targets.

## Database
- The platform's tables (`peptides`, its relation tables, `peptide_graph`, the lookups) belong to peptides-platform's Drizzle schema (XR-8). Never add, alter or drop a platform column from this repo, not in Alembic and not in a hand-run SQL file. The platform's Drizzle migration lands first; skill `platform-schema-dependency`.
- Alembic manages only this service's tables, `vendor_scrape_targets` and `vendor_price_observations`, with the version table `alembic_version_web_scrape`. `alembic/env.py` filters autogenerate to those two tables; keep it that way. One model file per owned table in `app/infrastructure/db/models/`.
- A new platform table with a `peptide_id` foreign key is added to `delete_peptide_cascading` (`app/repositories/peptide.py`) in the same release.
- Tests never use a `DATABASE_URL` from `.env`. Postgres tests use a throwaway Docker container and carry the `docker` marker.

## Errors and logging
- No blind `except Exception: pass`. Catch what you can handle; otherwise log with context and re-raise or raise a typed error. A background job that fails as a whole calls `capture_background_failure` (Sentry) once.
- Why: endpoints used to wrap every failure as `HTTPException(500, str(e))`, which leaked driver messages. The PK summary route hides them (`Failed to fetch PK summary.`); new routes do the same.
- Never log or echo `DATABASE_URL`, `API_TOKEN` or any `.env` value. New secret-like settings are added to `app/core/redaction.py`.

## Settings
- `app/core/config.py` (`Settings`, pydantic) is the only code that reads environment variables, apart from `DATABASE_URL`, which the pool and sync still read with `os.getenv`. A new setting goes into `Settings` and `.env.example` together.
- Never rename an environment variable; if one must change, keep accepting the old name (`AliasChoices`).
- Only one scheduler per database: staging pins `START_SCHEDULER=false`. Never turn on `VENDOR_SCRAPE_CRON_ENABLED` without an explicit decision for that environment.

## Tests
- The suite is offline: no live site, no real database, no network. Fixture pages live in `tests/vendors/fixtures/`.
- Each test sits in its theme folder with the theme's marker (`pytest.ini`). A new scraper adds a theme folder and a row in `tests/README.md`.
- Bug fixes start with a failing test at the service or extractor seam, using a fixture page.
