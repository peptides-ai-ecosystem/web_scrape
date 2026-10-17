# Workflow: deploy to staging

Only staging. `master` is production: never push or merge it without the words "release to production" from the user.

1. `scripts/check.sh` passes locally. CI is billed: push once, after the local gate.
2. Confirm the branch is based on current `origin/staging`.
3. Push to `staging` (or merge the PR into `staging`). The push runs `.github/workflows/deploy.yml`, which builds the image, runs `alembic upgrade head` for this service's two tables and rolls `web-scrape-staging` in the shared staging stack (`docs/ops/deploy.md`).
4. Watch the run, then `GET /health` on the staging gateway: its `commit` must be your sha.
5. Smoke `GET /web_scrape/api/v1/vendors/targets` through the gateway; expect 200 and the target list.
6. Staging boots idle: `START_SCHEDULER=false`, vendor cron and publisher off. Do not turn them on.
7. Never edit `.deploy/staging-*.sh` here (XR-11, shared byte for byte).

Verify: `/health` shows your commit and the smoke call returns 200. Report the run URL and the sha.
