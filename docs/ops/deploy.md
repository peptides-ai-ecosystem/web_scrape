# Deploy and error reporting

The EC2 host does **not** hold this repository. A push to `staging` deploys
`web-scrape-staging` in the shared staging stack (orchestrator's
`deploy/ms-staging/`). A push to `master` is a **production** deploy: it runs
`.github/workflows/deploy.yml`, which:

1. builds the image from the whole repository (Dockerfile) and pushes it to
   `ghcr.io/peptides-ai-ecosystem/web_scrape`, tagged with the commit sha;
2. copies `docker-compose.deploy.yml` to the box;
3. pulls that exact image and restarts the `web-scrape` container.

So on the box you will only find `~/web_scrape/docker-compose.deploy.yml` and
`.env`; the code is inside the container (`/app/app`, `/app/main.py`).

To see which code is live, call `GET /health`. Its `commit` field is the git
sha the running image was built from (FEEDBACK-3 G36). Then compare it with
`git log master -1`. On the box, `docker inspect web-scrape --format
'{{.Config.Image}}'` shows the same sha in the image tag.

**Error reporting (Sentry, FEEDBACK-3 G15).** Off unless `SENTRY_DSN` is set in
the box's `.env` (run the deploy workflow with `set_sentry_dsn`). It reports
5xx, timeouts and unhandled exceptions on API routes, scheduler jobs that raise,
and sync / competitor scrape runs that fail as a whole — never ordinary 4xx, and
never a single competitor page that fails to parse. Events are tagged
`service=web_scrape` plus the request's `X-Trace-Id`; credentials are scrubbed.

| Variable | Default | Meaning |
|---|---|---|
| `SENTRY_DSN` | empty | Empty = Sentry fully off (no init, no network) |
| `SENTRY_ENVIRONMENT` | `$ENVIRONMENT`, else `production` | Environment shown in Sentry |
| `SENTRY_RELEASE` | `$GIT_SHA` (baked in by the Dockerfile) | Release shown in Sentry |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Performance tracing; leave at 0 |

---

## Staging
- A push to `staging` deploys `web-scrape-staging` in orchestrator's `deploy/ms-staging/` (shared compose, `.deploy/` scripts shared byte-for-byte, XR-11). The staging compose pins `START_SCHEDULER=false`, `VENDOR_SCRAPE_CRON_ENABLED` off and `VENDOR_PRODUCTS_PUBLISH_ENABLED=false`: the container boots idle.
- The deploy runs `alembic upgrade head` in the container before recreating it (this service's two tables only, version table `alembic_version_web_scrape`).
- Production is `master` and deploys only on the words "release to production": the production deploy must run the same `alembic upgrade head` once (`docs/agents/commands.md`).
