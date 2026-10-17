# migrations/

web_scrape has no migration runner. Every file here is idempotent SQL (`IF NOT EXISTS` / `IF EXISTS` guards).

## Applied automatically

| File | Creates | How |
|---|---|---|
| `migration_vendor_price_observations.sql` | `vendor_price_observations` | On every startup by `app/infrastructure/db/vendor_schema.py` while `VENDOR_SCHEMA_AUTO_CREATE=true` (the default) |
| `migration_vendor_scrape_targets.sql` | `vendor_scrape_targets` | Same |

These are web_scrape's own tables. They are the only SQL files copied into the image (`Dockerfile`, `.dockerignore`). Moving or renaming them means updating both, plus `vendor_schema.py`; `app/tests/test_image_contents.py` checks all three.

## Applied by hand

These change tables that the platform's Drizzle schema owns (`peptides`, `peptide_graph`; cross-repo contract XR-8, `../orchestrator/docs/ecosystem/dependencies.md#xr-8`). Check the platform schema before running one; a column the platform does not declare is listed in `KNOWN_UNDECLARED_COLUMNS` in `app/tests/test_platform_schema_contract.py`.

| File | Changes |
|---|---|
| `migration_peptide_graph.sql` | creates `peptide_graph` and adds its `legend` column |
| `migration_add_activity_type_to_peptides.sql` | adds `peptides.activity_type` |
| `migration_add_molecular_fields_to_peptides.sql` | adds `peptides.molecular_type`, `molecular_length`, `molecular_weight` |
| `migration_change_contraindications_stop_signs_to_jsonb.sql` | changes `peptides.contraindications` and `stop_signs` to JSONB |

Run one against a database you are allowed to change (never production without the words "release to production"):

```bash
psql "$DATABASE_URL" -f migrations/<file>.sql
```
