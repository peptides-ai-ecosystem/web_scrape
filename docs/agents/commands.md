# Commands (web_scrape)

Run everything from the repo root. Python 3.12 via `uv`.

## Install
```bash
uv sync
cp .env.example .env      # point DATABASE_URL at a throwaway database
```

## Run
```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8005   # 8005 locally: chat uses 8000
uv run main.py                                          # binds $PORT, default 8000
```
Swagger `/docs`, gateway spec `/api/v1/openapi.json`, health `/health`, dashboard `/visualization/`. Set `START_SCHEDULER=false` to start without the background sync.

## Test
```bash
uv run pytest -q                                            # everything pytest collects
uv run pytest app/tests/test_vendor_ssrf.py -q              # one file
uv run pytest app/tests/test_image_contents.py::test_schema_files_exist_in_the_repo -q   # one test
PLATFORM_SCHEMA_REPO=<peptides-platform checkout> uv run pytest app/tests/test_platform_schema_contract.py -v
```
The suite is offline. Tests that need Chromium skip themselves; the platform-schema contract test skips without a platform checkout. `uv run pytest` also collects three tests that already fail on `staging`; `scripts/check.sh` lists and deselects them.

## Local gate
```bash
scripts/check.sh          # uv sync --frozen + the test suite (what CI runs)
```

## Lint and typecheck
None configured in this repo.

## Migrate
No migration runner. See `migrations/README.md`: the two vendor files run on startup; the others are applied by hand with `psql "$DATABASE_URL" -f migrations/<file>.sql`.
