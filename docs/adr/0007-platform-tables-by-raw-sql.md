# 0007 - Platform tables are written by raw SQL, never changed from here

Status: accepted (2026-10-18).

## Context
The pep-pedia sync fills the platform's `peptides`, relation and `peptide_graph` tables (XR-8). Drizzle in peptides-platform owns their schema; this service uses repository SQL against the platform database.

## Decision
No column or table is added to a platform table from this repo; the Drizzle migration lands first (skill `platform-schema-dependency`). Alembic here covers only `vendor_scrape_targets` and `vendor_price_observations` (ADR 0002). Writes are fill-empty-only by default. The vendored snapshot plus `KNOWN_UNDECLARED_COLUMNS` (ADR 0003) is the guard; the list must shrink to empty.

## Consequences
A platform rename or drop needs a consumer change in the same release. Enforced by: `tests/sync/test_platform_schema_contract.py`, `app/repositories/`.
