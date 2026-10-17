---
name: platform-schema-dependency
description: Use when changing SQL in web_scrape that touches a platform table (peptides, its relation tables, peptide_graph, the tables in delete_peptide_cascading), when adding a column to the sync payload, or when the platform's Drizzle schema changes. Explains the XR-8 contract and how to run the platform-schema contract test.
---

# web_scrape depends on the platform's database schema (XR-8)

web_scrape writes and deletes rows in the **peptides-platform** database with raw SQL. The platform owns those tables in its Drizzle schema (`apps/api/src/db/schema/`, migrations in `apps/api/drizzle/`). Contract: [XR-8](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/dependencies.md#xr-8) in the orchestrator repo.

## Where web_scrape touches platform tables
- `app/repositories/*.py` — inserts and updates (`_insert_guarded`, literal `UPDATE ... SET`).
- `app/infrastructure/db/service.py` — `link_relation(...)` and `insert_lookup(...)` (called from `app/services/sync/group_sync.py`) name the junction and lookup tables.
- `app/services/sync/group_b/peptide_mapper.py` — the keys of the dict it returns are the `peptides` columns written.
- `app/repositories/peptide.py` `delete_peptide_cascading` — hard-codes every platform table that references a peptide. A new platform table with a `peptide_id` foreign key must be added there, or the delete fails on the FK.
- Own tables (not platform): `vendor_price_observations`, `vendor_scrape_targets` (`migrations/`).

## Run the contract test
```bash
PLATFORM_SCHEMA_REPO=<path to a peptides-platform checkout on staging> \
  uv run pytest tests/sync/test_platform_schema_contract.py -v
```
- Default path: `G:/aultra/microservice/peptides-platform`. Without a checkout (as in CI) the test runs against the vendored snapshot `contracts/platform-schema/*.json`; with one it also fails when the snapshot is stale. After a platform change lands on staging, regenerate the snapshot with `scripts/export_platform_schema.py` and commit it.
- Use a checkout of the platform branch you will deploy with (normally `staging`); an old checkout proves nothing.
- It checks: every table in `delete_peptide_cascading` exists; every platform table named in web_scrape SQL exists; every column web_scrape inserts or updates is declared.

## When it fails
| Failure | Do |
|---|---|
| table missing | The platform renamed or dropped it. Do not edit the delete logic blindly: confirm with the platform change, then change both repos in the same release (owner first). |
| column web_scrape writes is undeclared | Either the platform must declare it (cross-repo change), or web_scrape must stop writing it. |
| "now declared by the platform" | Remove that pair from `KNOWN_UNDECLARED_COLUMNS`. |

`KNOWN_UNDECLARED_COLUMNS` lists columns that exist in the database only because `migrations/` adds them by hand (see `migrations/README.md`). Each is an open cross-repo item, not a permanent exception.

## Changing the schema
- Never add a platform column with a web_scrape SQL file. Ask for a Drizzle migration in peptides-platform; web_scrape follows in the same release.
- Hand-run SQL in `migrations/` is for databases you are allowed to change; production only after "release to production".
