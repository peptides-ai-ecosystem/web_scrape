---
name: debugging-a-scrape
description: Use when a web_scrape call or job fails - 401 or 502 through the gateway, a sync that stops on an unknown column, a vendor route that answers 500, a scrape job that ends with blocked or robots_disallowed readings, or a job stuck in running. Maps each symptom to its cause and the check that proves it.
---

# Debugging a scrape

Start from the symptom; confirm the cause with the check before changing code. Never print `DATABASE_URL`, `API_TOKEN` or any `.env` value (check a name is set with `grep -c '^NAME=.' .env`).

| Symptom | Cause | Check |
|---|---|---|
| 401 on every `/web_scrape/*` call | `API_TOKEN` here differs from the gateway's `API_TOKEN` (XR-10) | On the box: the gateway container's `API_TOKEN` and web_scrape's `.env` are written by the deploy workflow from the same value; redeploy rather than edit by hand |
| gateway 502/503 for `/web_scrape/*` | `WEBSCRAPE_SERVICE_URL` points at host port 8005 from inside Docker; the container listens on 8000 | `docker exec <gateway> printenv WEBSCRAPE_SERVICE_URL` should be `http://web-scrape-service:8000` (prod) or the staging service name on 8000 |
| sync fails with "column ... does not exist" or an unknown relation | the platform Drizzle schema changed (XR-8) | `PLATFORM_SCHEMA_REPO=<peptides-platform on staging> uv run pytest tests/sync/test_platform_schema_contract.py -v`; then skill `platform-schema-dependency` |
| vendor routes (admin Scrape tab) answer 500 right after a deploy | the Alembic revision for `vendor_scrape_targets` / `vendor_price_observations` was not applied to that database | `uv run alembic current` against that database shows no `4b1d0c2e9f10`; run `alembic upgrade head` (staging: the deploy's migrate step) or set `VENDOR_SCHEMA_AUTO_CREATE=true` |
| readings with status `blocked` or `robots_disallowed` | the site's robots.txt disallows the path, or it answered 403/429 | the observation's `failure_detail`. This is the correct outcome: record it and leave it. Never change the User-Agent, add proxies or retry around a block |
| readings flagged `low_confidence` / `price_delta` / `no_price` | selectors no longer match, or the price moved more than `VENDOR_PRICE_DELTA_THRESHOLD` | `POST /api/v1/vendors/discover` with the URL (dry run, nothing stored); fix the target's selectors with `PUT /targets/{slug}` |
| `POST /vendors/scrape` answers 409 | a scrape job is still pending or running (one run at a time) | `GET /api/v1/vendors/scrape/jobs`; cancel with `DELETE /api/v1/operations/job/{id}` |
| sync job never finishes or Chromium crashes | `/dev/shm` too small or Chromium missing in the environment | the compose file sets `shm_size: 2gb`; the image sets `CHROME_BIN`/`CHROMEDRIVER_BIN`; locally the Chromium tests skip themselves |
| a delete of a peptide fails on a foreign key | a new platform table references `peptides` | add it to `delete_peptide_cascading` (`app/repositories/peptide.py`) with the platform change |

## Where to look
- Job state: `GET /api/v1/operations/jobs?status=failed` and `GET /api/v1/operations/job/{id}` (in memory; cleared on restart).
- Logs: JSON lines on stdout with `trace_id`; the same id is on the Sentry event and on the gateway's log line (`X-Trace-Id`).
- Health: `GET /health` (commit sha), `GET /api/v1/operations/health` (job counts).

## Reproduce locally
Point `DATABASE_URL` at a throwaway database, run `uv run uvicorn main:app --port 8005` with `START_SCHEDULER=false`, and write the failing case as a test first: the fixture site under `tests/vendors/fixtures/` covers vendor pages offline.

## Steps

1. Take the symptom to the table above; run its check (never print a secret).
2. Read the job and the log line by `trace_id` (see "Where to look").
3. Write the failing case as a test first (see "Reproduce locally").
4. Fix the cause, run `uv run pytest -m <theme> -q`, then `scripts/check.sh`.
