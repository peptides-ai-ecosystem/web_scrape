# web_scrape — agent guide
Scrapes pep-pedia.org and competitor vendor sites, syncs peptide and PK-graph data into the platform database, and serves the sync, graph, evaluation, operations and vendor-pricing API (FastAPI + APScheduler, `main.py` -> `app/factory.py`).
It is an upstream behind the orchestrator gateway (`/web_scrape/*`); the platform admin and the peptide service call it.

Ecosystem map: [orchestrator AGENTS.md](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/AGENTS.md) (checkout `../orchestrator/docs/ecosystem/`) · contracts: [dependencies.md](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/dependencies.md). Canonical checkout: `G:\aultra\microservice\web_scrape`.

## Navigation
- `CODING_STANDARDS.md` — the rules a change is reviewed against (layering, scrapers, Alembic, settings).
- `docs/README.md` — the two scrapers and the pipeline; `docs/adding-a-scraper.md` — a new site.
- `app/api/v1/routers.py` + `app/api/v1/endpoints/` — every HTTP route; `app/api/gateway_auth.py` checks `X-Gateway-Token`.
- `app/scrapers/` (`pep_pedia/`, `vendors/`, `registry.py`) · `app/services/sync/` — CSV row -> platform tables, groups A–F (`docs/structured.md` is the insert order).
- `app/repositories/` — all SQL; `peptide.py` `delete_peptide_cascading` names the platform tables.
- `alembic/` — this service's two tables only; `migrations/README.md` — hand-run platform SQL that is waiting on the platform.
- `docs/features/` — one deep-dive per feature; `docs/ops/deploy.md` — AWS, Sentry, staging.

## Cross-repo
- [XR-8](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/dependencies.md#xr-8) consumer — writes the peptide and relation tables; deletes from every platform table that references a peptide. Skill `platform-schema-dependency`.
- XR-10 upstream — `/health`, `/api/v1/openapi.json`, `X-Gateway-Token`; port 8000 in the container, 8005 on the host.
- XR-11 consumer — `.deploy/staging-*.sh` are shared byte-for-byte copies (never edit); staging runs as `web-scrape-staging` in orchestrator's `deploy/ms-staging/`.
- XR-14 owner — HTTP API used by the platform (`apps/api/src/apps/admin-app/gateways/web-scrape.gateway.ts`) and peptide (`app/infrastructure/http/web_scrape_client.py`). Paths and JSON stay identical.

## Safety rules
- Work on `staging`. `master` is production: a push to it deploys production. Never push or merge to it without the words "release to production".
- Never print, echo or log secrets (`DATABASE_URL`, `API_TOKEN`, `.env` values).
- `DATABASE_URL` is a platform database: sync and delete endpoints change real platform rows. Point local runs at a throwaway database.
- Never add a platform column from this repo; the platform's Drizzle migration lands first (XR-8). Alembic here covers only `vendor_scrape_targets` and `vendor_price_observations`.
- Never run `scripts/ops/sync_supabase.sh`: it restores a database dump over its target.
- Only one scheduler per database: staging pins `START_SCHEDULER=false`; do not turn it on there.
- An empty `API_TOKEN` disables the gateway check; never deploy without it.

## When something breaks
Skill `debugging-a-scrape` (401, gateway 502, missing column, vendor 500, blocked hosts). Commands: `docs/agents/commands.md`; the local gate is `scripts/check.sh`.

## Skills
`.claude/skills/` — `platform-schema-dependency`, `adding-a-scraper`, `debugging-a-scrape`.
