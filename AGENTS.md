# web_scrape — agent guide
Scrapes pep-pedia.org and competitor vendor sites, syncs peptide and PK-graph data into the platform database, and serves the sync, graph, operations and vendor-pricing API (FastAPI + APScheduler, `main.py`).
It is an upstream behind the orchestrator gateway (`/web_scrape/*`); the platform admin and the peptide service call it.

Ecosystem map: `../orchestrator/docs/ecosystem/AGENTS.md` · contracts: `../orchestrator/docs/ecosystem/dependencies.md` ([GitHub](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/dependencies.md)). Canonical checkout: `G:\aultra\microservice\web_scrape`.

## Navigation
- `src/api/v1/routers.py` + `src/api/v1/endpoints/` — every HTTP route; `src/api/gateway_auth.py` checks `X-Gateway-Token`.
- `src/mappers/` — CSV row → platform tables, groups A–F (`docs/structured.md` is the insert order).
- `src/infrastructure/db/repositories/` — all SQL; `peptide.py` `delete_peptide_cascading` names the platform tables.
- `src/services/vendor_*` — competitor pricing; `vendor_products_publisher.py` is an unimplemented seam (`_send` raises).
- `migrations/README.md` — which SQL runs on startup and which by hand.
- `docs/features/` — one deep-dive per feature.

## Cross-repo
- [XR-8](../orchestrator/docs/ecosystem/dependencies.md#xr-8) consumer — writes the peptide and relation tables; `delete_peptide_cascading` deletes from every platform table that references a peptide. Skill `platform-schema-dependency`.
- [XR-10](../orchestrator/docs/ecosystem/dependencies.md#xr-10) upstream — `/health`, `/api/v1/openapi.json`, `X-Gateway-Token`; listens on 8000 in the container, 8005 on the host.
- [XR-11](../orchestrator/docs/ecosystem/dependencies.md#xr-11) consumer — `.deploy/staging-*.sh` are shared copies; staging runs as `web-scrape-staging` in orchestrator's `deploy/ms-staging/`.
- [XR-14](../orchestrator/docs/ecosystem/dependencies.md#xr-14) owner — HTTP API used by platform `apps/api/src/apps/admin-app/gateways/web-scrape.gateway.ts` (vendors, pk, graph, operations, sync) and peptide `app/infrastructure/http/web_scrape_client.py` (`sync/core`, `sync/graph`).

## Safety rules
- Work on `staging`. `master` is production: a push to it deploys production. Never push or merge to it without the words "release to production".
- Never print, echo or log secrets (`DATABASE_URL`, `API_TOKEN`, `.env` values).
- `DATABASE_URL` is a platform database: sync and delete endpoints change real platform rows. Point local runs at a throwaway database.
- Only one scheduler per database: staging pins `START_SCHEDULER=false`; do not turn it on there.
- An empty `API_TOKEN` disables the gateway check; never deploy without it.

## When something breaks
| Symptom | Likely cause |
|---|---|
| 401 on every `/web_scrape/*` call | `API_TOKEN` here differs from the gateway's (XR-10) |
| gateway 502/503 for `/web_scrape/*` | `WEBSCRAPE_SERVICE_URL` uses host port 8005 inside Docker; the container listens on 8000 |
| sync fails with an unknown column or relation | platform Drizzle schema changed (XR-8); run `src/tests/test_platform_schema_contract.py` |
| admin Scrape tab 500s at startup | vendor tables not created: `migrations/` files missing from the image or `VENDOR_SCHEMA_AUTO_CREATE=false` |
| peptide delete fails on a foreign key | a new platform table references `peptides`; add it to `delete_peptide_cascading` with the platform change |

## Commands and skills
- Commands: `docs/agents/commands.md`; the local gate is `scripts/check.sh`.
- Skills: `.claude/skills/` — `platform-schema-dependency`.
