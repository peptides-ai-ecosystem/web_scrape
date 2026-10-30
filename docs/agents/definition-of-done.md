# Definition of done (web_scrape)

A change is done when all of these hold:
- [ ] `scripts/check.sh` passes: ruff, ruff format, the mypy ratchet and the offline test suite.
- [ ] There is a test for the change in the matching `tests/<theme>/` folder (start with a failing one for a bug).
- [ ] The doc that describes the behaviour is updated in the same change; tracker labels stay out of docs.
- [ ] The OpenAPI path list is unchanged, or the change is a deliberate route change and lists the XR-14 consumers to update.
- [ ] SQL touching a platform table: the platform Drizzle column already exists on staging, `contracts/platform-schema/` is regenerated (`scripts/export_platform_schema.py`) and the contract test passes. No `KNOWN_UNDECLARED_COLUMNS` entry and no SQL file that changes a platform table.
- [ ] A new setting is in `app/core/config.py` and `.env.example`; no environment variable was renamed.
- [ ] No new ruff or mypy baseline entry; fixing a baselined file removes its line.
- [ ] Follow-ups for other repos (XR-8, XR-14) are listed in the PR description.
