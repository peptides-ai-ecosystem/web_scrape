# What web_scrape owns and consumes

Vendored from the ecosystem contract list in the orchestrator repo (dependencies.md: https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/dependencies.md). If a row here and that file disagree, that file wins; fix this one.

| XR | Role | What it means here |
|---|---|---|
| XR-14 | Owner | The HTTP API: `vendors/*`, `pk/peptides`, `graph/*`, `sync/{core,graph}`, `sync/peek` (+ `sync/peek/jobs/{id}`: reads one reference page, returns the mapped payload, writes nothing, AWD-17), `operations/*`. Competitor preview: `POST /vendors/discover` (sync, slow) or `POST /vendors/discover/jobs` + `GET /vendors/discover/jobs/{id}` (job, AID-2). Consumers: peptides-platform [apps/api/src/apps/admin-app/gateways/web-scrape.gateway.ts](https://github.com/peptides-apps/peptides-platform/blob/staging/apps/api/src/apps/admin-app/gateways/web-scrape.gateway.ts) and [peptide-microservice/app/infrastructure/http/web_scrape_client.py](https://github.com/peptides-ai-ecosystem/peptide-microservice/blob/staging/app/infrastructure/http/web_scrape_client.py). Paths, JSON keys and status codes stay identical; the OpenAPI path list is compared before and after a change. |
| XR-8 | Consumer | Raw SQL into the platform's Drizzle-owned tables: writes about 10 (`peptides`, relation and lookup tables, `peptide_graph`), and `delete_peptide_cascading` deletes from about 25. A platform rename or drop breaks it silently; the contract test `tests/sync/test_platform_schema_contract.py` runs against `contracts/platform-schema/`. Every column written here is declared by the platform; the four `peptides` columns once added by hand-run SQL (`activity_type`, `molecular_type`, `molecular_length`, `molecular_weight`) are platform Drizzle migration 0138 (webscrape-1), and `KNOWN_UNDECLARED_COLUMNS` is empty. |
| XR-10 | Upstream | `/health`, `/api/v1/openapi.json`, and `X-Gateway-Token` equal to the gateway's `API_TOKEN`. Port 8000 in the container, 8005 on the host and locally. The gateway reads `WEBSCRAPE_SERVICE_URL`. |
| XR-11 | Consumer | `.deploy/staging-*.sh` are byte-identical copies shared by the microservice repos; never edit them here. Staging runs as `web-scrape-staging` in the orchestrator repo's [deploy/ms-staging/](https://github.com/peptides-ai-ecosystem/orchestrator/tree/staging/deploy/ms-staging/). |
| R10 | Decision | Alembic here covers only this service's two tables; the first revision is a baseline that creates what is missing (`alembic_version_web_scrape`). |

## Business rules that shape the code
- We never store a placeholder price: an unreadable price or stock status is `None`, and a low-confidence reading is held for review (`app/scrapers/vendors/vendor_confidence.py`).
- Our own stores are never scraped as competitors (`app/core/owned_stores.py`).
- A robots.txt disallow, a 403 or a rate-limit refusal ends that host for the run; there is no bypass.
