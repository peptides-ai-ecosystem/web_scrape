# Commands (web_scrape)

Run everything from the repo root. Python 3.12 via `uv`.

## Install
```bash
uv sync
cp .env.example .env      # point DATABASE_URL at a throwaway database
```

## Run
```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8005   # the one place the port is stated: 8005 locally (chat uses 8000), 8000 in the container
```
Swagger `/docs`, gateway spec `/api/v1/openapi.json`, health `/health`, dashboard `/visualization/`. Set `START_SCHEDULER=false` to start without the background sync. `config/vendor_targets.json` is deployment config and is not committed: copy `config/vendor_targets.example.json` if you want a file seed.

## Test
```bash
uv run pytest -q                                      # everything
uv run pytest -m vendors -q                           # one theme (pep_pedia, vendors, sync, evaluation, ops)
uv run pytest tests/ops/test_image_contents.py -q     # one file
PLATFORM_SCHEMA_REPO=<peptides-platform checkout> uv run pytest tests/sync/test_platform_schema_contract.py -v
```
The suite is offline. Tests that need Chromium skip themselves; the platform-schema contract test skips without a platform checkout (run it locally when SQL touching a platform table changes); Docker tests skip without a daemon. `scripts/actual_ingestion.py` and `scripts/sync_pipeline.py` are manual scripts, not tests.

## Local gate
```bash
scripts/check.sh          # uv sync --frozen + the test suite (what CI runs)
```

## Lint and typecheck
None configured in this repo yet.

## Migrate (this service's own two tables only)
```bash
DATABASE_URL=postgresql://postgres:<pw>@127.0.0.1:<port>/<db> uv run alembic upgrade head
DATABASE_URL=... uv run alembic current        # shows 4b1d0c2e9f10 (head) when applied
```
The first revision is a baseline: it only creates what is missing, so it succeeds on a database where both tables already exist (staging, production) and records itself in `alembic_version_web_scrape`. The staging deploy runs `alembic upgrade head` in the container; production runs it once on "release to production". `VENDOR_SCHEMA_AUTO_CREATE=true` runs it at app startup instead (off by default). Test on a throwaway container: `docker run -d --rm -p 55432:5432 -e POSTGRES_PASSWORD=pw postgres:17`.

Platform SQL in `migrations/` is hand-run and waiting on peptides-platform's Drizzle migrations (`migrations/README.md`).
