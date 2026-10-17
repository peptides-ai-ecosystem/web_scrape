# tests/sync

Tests for writing into the platform tables: mapper groups A-F, fill-empty-only sync, and the platform schema contract (runs against the vendored snapshot `contracts/platform-schema/*.json`, or live against a peptides-platform checkout via PLATFORM_SCHEMA_REPO; regenerate with `scripts/export_platform_schema.py`).

Marker: `sync` (`uv run pytest -m sync`).
