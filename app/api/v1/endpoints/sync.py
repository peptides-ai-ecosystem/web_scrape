"""pep-pedia sync endpoints: validate the body, then one call to ``PepPediaSyncController``."""

from fastapi import APIRouter, BackgroundTasks

from app.api.errors import http_error
from app.controllers.peek_controller import PeekController
from app.controllers.pep_pedia_sync_controller import PepPediaSyncController
from app.core.errors import ServiceError
from app.models.sync import PeekRequest, SyncRequest

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/core", status_code=202)
async def start_core_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    🕷️ Scrape → Sync to **core** database tables.

    Triggers a background pipeline that:

    1. **Resolves URLs** — uses provided `urls` or auto-discovers via the peptide URL crawler
    2. **Scrapes** each page with Selenium (hero, quick-guide, community, section extractors)
    3. **Writes** scraped data to the master CSV
    4. **Reads** CSV rows and syncs to **core DB tables** (peptides, benefits, side_effects,
       dosages, schedules, administration methods, interactions, indications, protocols, references)

    ### Request Body
    - `urls`: explicit list of pep-pedia URLs, or `null` for auto-discovery
    - `limit`: cap the number of URLs (useful for testing)
    - `fill_empty_only`: `true` = only fill empty peptide columns and add child-row kinds the
      peptide has none of; never overwrite curated values (used after research approve)

    ### Responses
    - **202** → Accepted. Returns a `job_id` — poll `/api/v1/operations/job/{job_id}` for status.
    - **422** → Validation error (e.g., `limit` ≤ 0, invalid types)
    - **500** → `DATABASE_URL` environment variable not configured on the server.

    ### Example
    ```json
    {"limit": 5, "urls": null}
    ```
    """
    try:
        return PepPediaSyncController(background_tasks.add_task).start_core(request)
    except ServiceError as exc:
        raise http_error(exc)


@router.post("/graph", status_code=202)
async def start_graph_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    🕷️ Scrape → Sync to **graph** database tables.

    Triggers a background pipeline that:
    1. Resolves URLs (provided or auto-discovered)
    2. Scrapes each page with Selenium
    3. Syncs pharmacokinetics graph data to `peptide_graph` table

    **Only syncs graph data for peptides already present** in the core `peptides` table.

    With `fill_empty_only: true`, a peptide that already has PK curves is skipped, so
    existing curves are never overwritten.

    ### Responses
    - **202** → Accepted. Returns a `job_id` for polling.
    - **422** → Validation error (invalid `limit` or `urls`).
    - **500** → `DATABASE_URL` not configured.

    ### Example
    ```json
    {"urls": ["https://pep-pedia.org/peptide/1"], "limit": null}
    ```
    """
    try:
        return PepPediaSyncController(background_tasks.add_task).start_graph(request)
    except ServiceError as exc:
        raise http_error(exc)


@router.post("/graph-missing", status_code=202)
async def start_graph_sync_missing(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    🕷️ Scrape → Sync **only missing** graph data.

    Same as `/graph` but **only inserts administration methods that don't yet exist**
    in the `peptide_graph` table. Idempotent — safe to run repeatedly.

    ### Use Case
    After a full graph sync, run this periodically to pick up any new administration
    methods without re-processing existing data.

    ### Responses
    - **202** → Accepted. Returns a `job_id` for polling.
    - **422** → Validation error.
    - **500** → `DATABASE_URL` not configured.

    ### Example
    ```json
    {"limit": 10, "urls": null}
    ```
    """
    try:
        return PepPediaSyncController(background_tasks.add_task).start_graph_missing(request)
    except ServiceError as exc:
        raise http_error(exc)


@router.post(
    "/peek",
    status_code=202,
    responses={
        202: {"description": "Peek started; poll /sync/peek/jobs/{job_id}."},
        409: {"description": "Other pages are being read right now."},
        422: {"description": "URL is not https on a configured reference host."},
    },
)
async def start_peek(request: PeekRequest, background_tasks: BackgroundTasks):
    """
    🔎 Read ONE reference page and show what a core sync would write. **Nothing is stored.**

    Scrapes the page in memory (its own browser, no shared CSV, no database) and runs the
    sync mappers over it. The job `result` holds the mapped peptide columns, benefits, side
    effects, child-row counts, the page's research stage (a maturity label, not a legal
    status) and warnings. The caller compares it with its own data and applies only what an
    admin picks.

    Only `https` URLs on `PEEK_ALLOWED_HOSTS` (default pep-pedia.org) are read; anything else
    is a **422**. Returns **202** with a `job_id`; poll `GET /sync/peek/jobs/{job_id}`.
    """
    try:
        return PeekController(background_tasks.add_task).start(request.url)
    except ServiceError as exc:
        raise http_error(exc)


@router.get("/peek/jobs/{job_id}", responses={404: {"description": "Unknown peek job."}})
async def get_peek_job(job_id: str):
    """Status and, once completed, the mapped payload of one peek (`result`)."""
    try:
        return PeekController.get_job(job_id)
    except ServiceError as exc:
        raise http_error(exc)
