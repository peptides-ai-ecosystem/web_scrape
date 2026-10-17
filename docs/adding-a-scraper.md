# Adding a scraper

A new site is one new package in this service, not a new repository. A new **competitor** for the vendor scraper is not a new scraper: add a target through the API (`POST /api/v1/vendors/targets` or `/targets/from-url`).

Agents: skill `adding-a-scraper` (`.claude/skills/adding-a-scraper/SKILL.md`) has the same steps.

1. **Package** — `app/scrapers/<name>/`, site-specific code only (discovery, extraction). Fetch through `app/infrastructure/`: `PoliteHttpClient` or `PlaywrightPageFetcher`, `RobotsPolicy`, `HostRateLimiter`, `url_safety.check_url`. No FastAPI import, no SQL (`CODING_STANDARDS.md`).
2. **Registry** — one `ScraperInfo` line in `app/scrapers/registry.py`.
3. **Storage**
   - writes platform tables → a mapper in `app/services/sync/` and SQL in `app/repositories/`; any new platform column is a Drizzle migration in peptides-platform first (skill `platform-schema-dependency`);
   - stores its own rows → one model file per table in `app/infrastructure/db/models/`, the names in `OWN_TABLES`, and an Alembic revision (`uv run alembic revision -m "<what>"`), tested on a throwaway Postgres.
4. **Routes** (only for a new HTTP feature) — models in `app/models/<name>.py`, a controller in `app/controllers/` that runs the scrape and the write, an endpoint module registered in `app/api/v1/routers.py`. Each route is a status mapping plus one call.
5. **Tests** — `tests/<name>/` with a `README.md`, a marker in `pytest.ini`, offline fixture pages, and a row in `tests/README.md`.
6. **Docs** — a row in `docs/README.md`.

Done when `scripts/check.sh` passes, its tables are an Alembic revision, and the platform-schema contract test still passes.
