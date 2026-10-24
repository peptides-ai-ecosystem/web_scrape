# Troubleshooting (web_scrape)

| Symptom | Look at |
|---|---|
| Add competitor preview says "Upstream service 'web_scrape' timed out" | The synchronous `POST /vendors/discover` paces itself (5 s per store request) and outlasts the gateway timeout. Use `POST /vendors/discover/jobs` and poll `GET /vendors/discover/jobs/{id}`; the gateway's `PROXY_TIMEOUT_WEB_SCRAPE` only matters for the old route. |
| Gateway 502 for `/web_scrape/*` | Port: the container listens on 8000, the host publishes 8005. `WEBSCRAPE_SERVICE_URL` in the gateway must match. |
| 401 on every call | `X-Gateway-Token` must equal the gateway's `API_TOKEN`; an empty `API_TOKEN` here is a **503 "Authentication is not configured"** on every `/api/v1` call (fail closed; `/health` stays open). Locally without a gateway: `ALLOW_UNAUTHENTICATED=true` and `ENVIRONMENT=local`. |
| `column ... does not exist` or a sync failing after a platform release | XR-8 drift: run the contract test against a fresh platform checkout, regenerate `contracts/platform-schema/`, fix the SQL in `app/repositories/`. Never add the column from here. |
| Contract test says the snapshot is stale | Run `scripts/export_platform_schema.py` from a platform checkout on `staging` and commit the JSON. |
| Vendor scrape returns `blocked`, `robots_disallowed` or `skipped` | Intended: the host refused us. Do not rotate user agents or proxies (`CODING_STANDARDS.md`). |
| Vendor target 500 or a missing table | `alembic upgrade head` has not run on that database (`docs/agents/commands.md`), or `VENDOR_SCHEMA_AUTO_CREATE` is off. |
| Jobs run twice or never | One scheduler per database; staging pins `START_SCHEDULER=false`. |
| A Chromium test skips locally | Expected without Chromium; the suite stays green. |
| Staging deploy of one service broke another | XR-11: the `.deploy` copies differ; check with [orchestrator/scripts/ecosystem/check-shared-deploy.sh](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/scripts/ecosystem/check-shared-deploy.sh). |

Skill `debugging-a-scrape` walks the first five in order.
