# web_scrape — agent guide
Scrapes pep-pedia.org and competitor vendor sites, syncs peptide and PK-graph data into the platform database, and serves the sync, graph, evaluation, operations and vendor-pricing API (FastAPI + APScheduler, `main.py` -> `app/factory.py`). An upstream behind the orchestrator gateway at `/web_scrape/*`; the platform admin and the peptide service call it. Work on `staging`; `master` is production.

Ecosystem map and contracts (GitHub): [AGENTS.md](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/AGENTS.md) · [dependencies.md](https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/dependencies.md).

## Navigation
- `docs/agents/architecture.md` — the three paths (scrape, sync, vendor), the API and the scheduler, one line per hop.
- `docs/agents/business.md` — what this service owns (XR-14) and consumes (XR-8, XR-10, XR-11).
- `docs/agents/commands.md` — every command: install, run and the port, gate, tests, migrate.
- `CODING_STANDARDS.md` — the rules a change is reviewed against. `docs/agents/definition-of-done.md` — what done means.
- `GLOSSARY.md` and `docs/adr/` — terms and decisions (`docs/agents/domain.md`).
- `app/api/v1/routers.py` — every route; `app/repositories/peptide.py` `delete_peptide_cascading` names every platform table that references a peptide.
- `docs/product/sync-schema.md` — insert order, relations and field mapping for mapper groups A–F; `migrations/README.md` — hand-run platform SQL waiting on the platform.

## Workflows (read the one that matches)
- New feature or route change → `docs/agents/workflows/new-feature.md`
- Bug fix → `docs/agents/workflows/fix-bug.md` · tests → `docs/agents/workflows/testing.md`
- SQL on a platform table, or a platform schema change → skill `platform-schema-dependency` + `docs/agents/workflows/schema-change.md`
- Deploy to staging → `docs/agents/workflows/deploy.md`
- A new site to scrape → skill `adding-a-scraper`
- A mapper (group A-F) change → `docs/agents/workflows/mapper-change.md`
- A competitor vendor target → `docs/agents/workflows/vendor-target.md`
- Automatic (Claude Code Workflow tool): `.claude/workflows/run-ticket.js` (one issue to a staging PR) and `.claude/workflows/intake-feedback.js` (feedback text to issues); steps: `docs/agents/workflows/run-ticket.md`, `docs/agents/workflows/intake-feedback.md`

## Issues
GitHub issues on peptides-ai-ecosystem/web_scrape (`docs/agents/issue-tracker.md`); labels in `docs/agents/triage-labels.md`.

## Skills (`.claude/skills/`; how to use them: `docs/agents/skills.md`)
| Skill | Use when |
|---|---|
| `adding-a-scraper` | a new kind of site (a source, not a competitor target) needs a package |
| `add-a-vendor-target` | adding or changing a competitor target or how it is read |
| `change-a-mapper` | a sync mapper, lookup or relation (groups A-F) changes |
| `platform-schema-dependency` | SQL touches a platform table or the platform schema changes (XR-8) |
| `debugging-a-scrape` | a call or job fails: 401/502, unknown column, blocked readings, stuck job |

## Safety rules
- Never push or merge `master` without the words "release to production"; a push to it deploys production.
- Never print, echo or log secrets (`DATABASE_URL`, `API_TOKEN`, `.env` values).
- `DATABASE_URL` is a platform database: sync and delete endpoints change real rows. Point local runs at a throwaway database.
- Never add a platform column from this repo; the platform's Drizzle migration lands first (XR-8). Alembic here covers only `vendor_scrape_targets` and `vendor_price_observations`.
- Never run `scripts/ops/sync_supabase.sh`: it restores a database dump over its target.
- One scheduler per database: staging pins `START_SCHEDULER=false`. An empty `API_TOKEN` disables the gateway check; never deploy without it.

Something broken? `docs/agents/troubleshooting.md` · skill `debugging-a-scrape` · gate `scripts/check.sh`
