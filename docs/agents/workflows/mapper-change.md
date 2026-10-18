# Workflow: change a sync mapper (groups A-F)

Mappers turn one CSV row into rows of the platform's tables (XR-8). The platform owns those tables.

1. Read `docs/agents/architecture.md` section 2 and the insert order in `docs/product/sync-schema.md`. Groups are written A to F so foreign keys resolve; never reorder.
2. Find the mapper: `app/services/sync/group_a/` lookups, `group_b/` peptide, `group_c/` relations, `group_d/` protocols and graph, `group_e/` details. SQL stays in `app/repositories/` (one file per platform table).
3. Does the change need a column or table that the platform does not declare? Stop: that is a Drizzle migration in peptides-platform first (skill `platform-schema-dependency`, `docs/agents/workflows/schema-change.md`). Never add a column from this repo.
4. Write the failing test first in `tests/sync/` (`test_mapping_groups.py`, `test_sync_fill_empty_only.py`). Sync is fill-empty-only unless the request says otherwise; keep that behaviour and test it.
5. Implement. A renamed or newly written column changes `contracts/platform-schema/` expectations: run `tests/sync/test_platform_schema_contract.py`; it must run against the snapshot, not skip.
6. If a platform table gained a reference to `peptides`, add it to `delete_peptide_cascading` (`app/repositories/peptide.py`).
7. Update the doc that describes the mapping and list XR-8 / XR-14 follow-ups in the PR.

Verify: `uv run pytest -m sync -q`, then `scripts/check.sh`; `docs/agents/definition-of-done.md` is ticked.
