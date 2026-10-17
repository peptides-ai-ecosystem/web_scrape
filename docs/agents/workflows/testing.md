# Workflow: running and adding tests

The suite is offline: no live site, no real database, no network. Never point a test at a `DATABASE_URL` from `.env`; Postgres tests use a throwaway Docker container and carry the `docker` marker.

Run:
```bash
scripts/check.sh                                   # ruff, format, mypy ratchet, full suite (what CI runs)
uv run pytest -m vendors -q                        # one theme: pep_pedia, vendors, sync, evaluation, ops
uv run pytest tests/ops/test_image_contents.py -q  # one file
```
Full runs and Docker tests are heavy: if another agent holds the shared lock `C:/tmp/heavy-py.lock`, wait for it.

Add:
1. Put the test in the folder of its theme (`tests/README.md`); the folder's marker is applied by `tests/conftest.py`.
2. Use the fixtures, fakes and recorded pages that exist (`tests/vendors/fixtures/`); do not add a live request.
3. Chromium-only tests skip themselves; keep that guard.
4. A test of SQL against a platform table also runs the contract test (`tests/sync/test_platform_schema_contract.py`) against `contracts/platform-schema/`.

Verify: the new test fails when the behaviour is broken; `scripts/check.sh` passes.
