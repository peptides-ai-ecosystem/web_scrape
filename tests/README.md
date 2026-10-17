# tests

The suite is offline: no live site, no real database, no network. Tests that need Chromium skip themselves; tests that need Docker carry the `docker` marker and skip without a daemon. Run it with `scripts/check.sh`.

| Theme (folder, marker) | Covers |
|---|---|
| `tests/pep_pedia/` (`pep_pedia`) | graph extractor, graph and core-data read APIs, PK summary, CSV inspector |
| `tests/vendors/` (`vendors`) | url discovery, vendor scrape, SSRF guard, targets API, confidence (fixture pages in `tests/vendors/fixtures/`) |
| `tests/sync/` (`sync`) | mapper groups, fill-empty-only sync, platform schema contract (XR-8) |
| `tests/evaluation/` (`evaluation`) | CSV versus database evaluation API |
| `tests/ops/` (`ops`) | jobs and health, gateway token, Sentry, image contents, Alembic baseline |

`tests/conftest.py` marks each test with its folder's theme: `uv run pytest -m vendors`.

Every new scraper adds a folder beside `pep_pedia/` and `vendors/`, a marker in `pytest.ini`, a theme README and a row in this table (`docs/adding-a-scraper.md`).
