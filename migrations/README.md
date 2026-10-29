# migrations/

**Owner: peptides-platform.** Every file here changes the platform's `peptides` table, which belongs to the platform's Drizzle schema (XR-8). web_scrape does not own or run these files. They stay here only until the platform declares the columns, and they are not shipped in the Docker image.

web_scrape's own tables, `vendor_scrape_targets` and `vendor_price_observations`, are an Alembic revision (`alembic/versions/`, version table `alembic_version_web_scrape`, decision R10). See `docs/agents/commands.md` for how to run it.

## What is left and why

web_scrape still writes these columns, and the platform's Drizzle schema on `staging` does not declare them (checked 29 Oct). Without them, a database built from Drizzle alone fails the sync. So two files stay:

| File | Adds | web_scrape writes it in |
|---|---|---|
| `migration_add_activity_type_to_peptides.sql` | `peptides.activity_type` | `app/repositories/peptide.py` `update_activity_type` |
| `migration_add_molecular_fields_to_peptides.sql` | `peptides.molecular_type`, `molecular_length`, `molecular_weight` | `app/services/sync/group_b/peptide_mapper.py` |

These four columns are `KNOWN_UNDECLARED_COLUMNS` in `tests/sync/test_platform_schema_contract.py`.

Removed (webscrape-1):
- `migration_change_contraindications_stop_signs_to_jsonb.sql`: web_scrape writes JSON text (`json.dumps`) into `contraindications` and `stop_signs`, and Drizzle's `text` holds it. The column type is the platform's decision, not a web_scrape prerequisite.
- `migration_peptide_graph.sql`, earlier: Drizzle declares `peptide_graph` with `legend` and `action_type` (platform migrations 0095, 0096).

## Follow-up (platform first, then here)

1. peptides-platform adds the four columns to `apps/api/src/db/schema/modules/shared/peptides/peptides.ts` with an additive Drizzle migration (proposed as 0137). It uses `ADD COLUMN IF NOT EXISTS`, so databases that already ran these files are unchanged. This is tracked in peptides-platform issue #522 ([XR-8], ADR 0009).
2. Once it is on staging, delete both files and this table, remove the four pairs from `KNOWN_UNDECLARED_COLUMNS`, and regenerate `contracts/platform-schema/` (`scripts/export_platform_schema.py`). Then delete `migrations/` entirely.

Do not add new files here: a new platform column goes into a platform Drizzle migration first (`docs/agents/workflows/schema-change.md`).

Until then, run a file only against a database you are allowed to change (never production without the words "release to production"):

```bash
psql "$DATABASE_URL" -f migrations/<file>.sql
```
