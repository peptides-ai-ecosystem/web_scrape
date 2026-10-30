# Workflow: SQL that touches a platform table, or a platform schema change

The platform's Drizzle schema owns `peptides`, its relation tables, the lookups and `peptide_graph` (XR-8). This repo never adds, alters or drops a platform column, in Alembic or in a hand-run SQL file. Read skill `platform-schema-dependency` first.

1. Check whether the column or table is in `contracts/platform-schema/` (the vendored snapshot). If it is, write the SQL in `app/repositories/`.
2. If it is not, stop. Open an `[XR-8]` issue in peptides-platform asking for the Drizzle declaration and wait for its migration to land on staging. Do not write a SQL file for it here; do not add a `KNOWN_UNDECLARED_COLUMNS` entry.
3. A new platform table with a `peptide_id` foreign key goes into `delete_peptide_cascading` (`app/repositories/peptide.py`) in the same change.
4. After the platform change is on staging, run `scripts/export_platform_schema.py` from a platform checkout on `staging`, review the JSON diff and commit it.
5. The contract test must run, not skip: `uv run pytest tests/sync/test_platform_schema_contract.py -v`.
6. Release order is recorded in the PR: platform first, this service after.

Only this service's own tables (`vendor_scrape_targets`, `vendor_price_observations`) change through Alembic (`alembic/versions/`, `docs/adr/0002-alembic-scope.md`).

Verify: contract test passes without a skip, `scripts/check.sh` passes, the PR names the platform issue.
