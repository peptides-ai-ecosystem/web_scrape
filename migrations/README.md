# migrations/

Hand-run SQL for tables the **platform** owns. web_scrape does not migrate them (XR-8): they belong to peptides-platform's Drizzle schema. These files are not shipped in the Docker image.

web_scrape's own tables, `vendor_scrape_targets` and `vendor_price_observations`, are an Alembic revision (`alembic/versions/`, version table `alembic_version_web_scrape`, decision R10). See `docs/agents/commands.md` for how to run it.

| File | Changes | Drizzle status (staging, 15 Oct) |
|---|---|---|
| `migration_add_activity_type_to_peptides.sql` | adds `peptides.activity_type` | not declared: the platform must add it |
| `migration_add_molecular_fields_to_peptides.sql` | adds `peptides.molecular_type`, `molecular_length`, `molecular_weight` | not declared: the platform must add them |
| `migration_change_contraindications_stop_signs_to_jsonb.sql` | changes `peptides.contraindications` and `stop_signs` to JSONB | Drizzle declares `text`: the platform must decide the type |

`migration_peptide_graph.sql` was deleted: Drizzle declares `peptide_graph` with `legend` and `action_type` (migrations 0095, 0096). The four undeclared `peptides` columns are `KNOWN_UNDECLARED_COLUMNS` in `tests/sync/test_platform_schema_contract.py`. Each file goes away when the platform's Drizzle migration lands; do not add new ones.

Run one against a database you are allowed to change (never production without the words "release to production"):

```bash
psql "$DATABASE_URL" -f migrations/<file>.sql
```
