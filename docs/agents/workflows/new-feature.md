# Workflow: new feature or route change

1. Read `CODING_STANDARDS.md` and `docs/agents/architecture.md`. A new site to scrape is a new scraper: use skill `adding-a-scraper`, not this file.
2. Decide the layers: model in `app/models/<feature>.py`, endpoint in `app/api/v1/endpoints/`, logic in `app/services/` (or a controller if it coordinates a scrape plus a write), SQL in `app/repositories/`.
3. Record the OpenAPI path list before you start: `uv run python -c "from main import app; print(sorted(app.openapi()['paths']))"`.
4. Write the failing test first in the matching `tests/<theme>/` folder.
5. Implement. The endpoint is a status mapping plus one call; it contains no SQL and no business logic.
6. A new route or changed JSON is an XR-14 change: the platform admin and the peptide service call this API. List the consumer follow-ups.
7. A new setting goes into `app/core/config.py` and `.env.example` together.
8. Update the doc that describes the behaviour.

Verify: `scripts/check.sh` passes; the path list differs only by the routes you meant to add; `docs/agents/definition-of-done.md` is ticked.
