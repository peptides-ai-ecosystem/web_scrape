# 0005 - One scheduler per database

Status: accepted (2026-10-18).

## Context
`app/core/scheduler.py` (APScheduler) runs the pep-pedia sync and the optional vendor cron inside the API process. Two instances against one database would run every job twice and write the same platform rows twice.

## Decision
Exactly one process per database starts the scheduler (`START_SCHEDULER`). Staging pins `START_SCHEDULER=false`; production runs one instance. The vendor cron is opt-in per environment (`VENDOR_SCRAPE_CRON_ENABLED`). Jobs are tracked by `app/core/job_queue.py` so the polling endpoints work without a second worker.

## Consequences
Scaling the API horizontally needs the scheduler moved out first. Enforced by: `docs/agents/commands.md` and the staging pin in `.github/workflows/deploy.yml`.
