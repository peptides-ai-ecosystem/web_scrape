# web_scrape

Scrapes pep-pedia.org and competitor vendor sites, syncs peptide and PK-graph data into the platform database, and serves the sync, graph, evaluation, operations and vendor-pricing API (FastAPI + APScheduler). It runs behind the orchestrator gateway at `/web_scrape/*`; the platform admin and the peptide service call it.

Two scrapers live here (`docs/README.md`): **pep_pedia** (peptide pages -> CSV -> the platform's peptide and PK-graph tables) and **vendors** (competitor product pages -> price observations in this service's own tables). A new site is a new package under `app/scrapers/` (`docs/adding-a-scraper.md`).

## Layout

```
main.py                      app = create_app()  (container: uvicorn main:app)
app/factory.py               the app, lifespan, middleware, /visualization mount
app/api/v1/endpoints/        routes: status codes and one call downward
app/controllers/             use cases that scrape and write (pep-pedia sync, vendor scrape)
app/services/                business rules; app/services/sync/ = CSV -> platform tables (groups A-F)
app/scrapers/                pep_pedia/ and vendors/ (+ registry.py)
app/repositories/            all SQL, one file per table
app/infrastructure/          DB pool, Playwright, Selenium, polite HTTP, robots, rate limiter, SSRF guard
app/core/                    settings, logging, auth, Sentry, errors, job queue, scheduler
app/models/                  Pydantic request and response models
app/visualization/           operator dashboard (served at /visualization)
alembic/                     revisions for this service's own two tables
tests/<theme>/               pep_pedia, vendors, sync, evaluation, ops (tests/README.md)
```

## Run

```bash
uv sync
cp .env.example .env     # point DATABASE_URL at a throwaway database
uv run uvicorn main:app --host 127.0.0.1 --port 8005
```

Swagger `/docs`, gateway spec `/api/v1/openapi.json`, health `/health`, dashboard `/visualization/`. Locally use port 8005 (chat uses 8000); the container listens on 8000. `START_SCHEDULER=false` starts without the background sync (staging pins it).

Docker: `docker build -t web_scrape .` then `docker run -p 8005:8000 --env-file .env web_scrape`. The image carries Chromium for the Selenium scrape and the Playwright vendor fetch.

## Gate

`scripts/check.sh` (uv sync + the offline test suite; this is what CI runs). All commands: `docs/agents/commands.md`.

## Docs

`docs/README.md` indexes the rest: the pipeline, the feature deep dives, the mapper docs, `docs/ops/deploy.md` (AWS, Sentry, staging), `AGENTS.md` and `CODING_STANDARDS.md` for agents and reviewers.
