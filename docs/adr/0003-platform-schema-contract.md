# 0003 - A vendored platform-schema snapshot backs the XR-8 contract test

Status: accepted (WS-C3).

## Context
web_scrape writes and deletes rows in platform tables with raw SQL (XR-8). The contract test that catches Drizzle drift needed a local platform checkout, so it skipped in CI and never gated a pull request.

## Decision
- `scripts/export_platform_schema.py` reads the Drizzle schema from a platform checkout and writes `contracts/platform-schema/<date>.json`: the columns of only the tables this service uses.
- `tests/sync/test_platform_schema_contract.py` uses a platform checkout when one exists (and then fails if the snapshot is stale against it); otherwise it uses the snapshot. It runs in CI.
- `KNOWN_UNDECLARED_COLUMNS` holds columns written here but not declared by the platform. It is empty since platform Drizzle 0138 declared the last four `peptides` columns (webscrape-1, 30 Oct 2026) and must stay empty: a new entry needs an `[XR-8]` issue in peptides-platform first.

## Consequences
The snapshot is regenerated, reviewed and committed whenever the platform schema or this service's SQL changes. A better long-term source is a platform-published schema export (an XR-8 platform issue); until then the parser reads the Drizzle files directly.
