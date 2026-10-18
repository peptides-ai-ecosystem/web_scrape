# Workflow: add or change a competitor vendor target

A competitor is data, not code. Do not add a scraper package for it (that is skill `adding-a-scraper`).

1. A target lives in the `vendor_scrape_targets` table, managed through `POST/PUT/DELETE /api/v1/vendors/targets`. A selector-free draft starts from `POST /api/v1/vendors/targets/from-url`, shows readings with `POST /api/v1/vendors/discover` (nothing stored), and runs only after `.../approve`. `config/vendor_targets.example.json` is the shape of an optional file seed; the real `config/vendor_targets.json` is local and git-ignored.
2. Our own stores are refused as targets; URLs must be public (the SSRF guard, `app/infrastructure/url_safety.py`). Never set `VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS` outside a local test.
3. Changing how a target is read (selectors, discovery, confidence, delta review) happens in `app/scrapers/vendors/`. Write a failing test in `tests/vendors/` against a recorded fixture page (`tests/vendors/fixtures/`); no test contacts a real competitor site.
4. Politeness is not optional: robots.txt first, per-host rate limit, no evasion. Do not lower a floor or bypass `PoliteHttpClient` / `RobotsPolicy` / `HostRateLimiter`.
5. A new column on `vendor_scrape_targets` or `vendor_price_observations` is an Alembic revision (`uv run alembic revision -m "<what>"`) tested on a throwaway Postgres. Writing to a platform table is a different path: see `schema-change.md`.
6. The API is XR-14: a changed route or JSON key needs the platform and peptide follow-ups listed in the PR. `vendor_products_publisher.py` is an unimplemented seam; do not wire it without the platform endpoint.

Verify: `uv run pytest -m vendors -q`, then `scripts/check.sh`. Before trusting a new target, run `POST /api/v1/vendors/discover` on staging, never on a production database.
