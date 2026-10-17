# 0002 - Alembic covers only this service's two tables

Status: accepted (decision R10, code review of 17 October 2026).

## Context
Two vendor tables were created by SQL executed on every boot; the rest of the database belongs to the platform. Staging and production databases already contain both tables.

## Decision
- Alembic manages `vendor_scrape_targets` and `vendor_price_observations` only, with the version table `alembic_version_web_scrape` so it cannot collide with another service on a shared database.
- `alembic/env.py` filters autogenerate to those two tables.
- The first revision is a baseline that creates only what is missing, so existing databases upgrade in place. Staging runs `alembic upgrade head` in its deploy; production runs it once on "release to production". `VENDOR_SCHEMA_AUTO_CREATE=true` runs it at startup instead (off by default).
- Platform tables are never touched by Alembic here.

## Consequences
The boot-time SQL runner is gone. Hand-run SQL in `migrations/` for platform tables is a stop-gap that disappears when the platform declares those columns (ADR 0003).
