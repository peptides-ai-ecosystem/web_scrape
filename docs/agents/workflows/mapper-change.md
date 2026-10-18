# Workflow: change a sync mapper (groups A-F)

Follow skill `change-a-mapper` (read the insert order, find the mapper, platform column first, failing test in `tests/sync/`, contract test must not skip, `delete_peptide_cascading`, docs).

Always: groups run A to F and are never reordered; sync is fill-empty-only; never add a platform column from this repo (XR-8).

Verify: `uv run pytest -m sync -q`, then `scripts/check.sh`; `docs/agents/definition-of-done.md` is ticked.
