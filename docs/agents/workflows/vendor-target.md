# Workflow: add or change a competitor vendor target

Follow skill `add-a-vendor-target` (target API, SSRF guard, fixture-page tests, politeness, Alembic for owned tables, XR-14 follow-ups).

Always: a competitor is data, not code; robots.txt first and a per-host rate limit; no test contacts a real site.

Verify: `uv run pytest -m vendors -q`, then `scripts/check.sh`.
