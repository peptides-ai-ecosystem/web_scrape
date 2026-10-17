## What and why

## Checklist (docs/agents/definition-of-done.md)
- [ ] `scripts/check.sh` passes
- [ ] Test added in `tests/<theme>/`
- [ ] Docs updated; OpenAPI path list unchanged (or the route change is intended and XR-14 consumers are listed)
- [ ] Platform tables: column exists on staging, `contracts/platform-schema/` regenerated, contract test ran (no skip)
- [ ] No new env var renamed; new settings in `app/core/config.py` and `.env.example`
- [ ] No new ruff or mypy baseline entry

## Cross-repo follow-ups
<!-- XR-8 / XR-14 issues in other repos, and the release order -->

## Production impact
<!-- env vars, migrations, deploy steps; production is `master` and needs "release to production" -->
