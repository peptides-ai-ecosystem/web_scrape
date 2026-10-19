# Run a ticket automatically (workflow `run-ticket`)

The script `.claude/workflows/run-ticket.js` takes one GitHub issue of peptides-ai-ecosystem/web_scrape to an open pull request against `staging`, with a review pass in between. It never merges.

## Start it
- Claude Code (this folder as the working directory): `Workflow({name:'run-ticket', args:{issue:123}})`. Plan only, nothing changed: add `dryRun:true`. You can also ask in plain words: "run ticket 123 with the run-ticket workflow".
- Cursor: Cursor does not run Claude Code Workflow scripts. Either open a terminal here and start Claude Code, or do the checklist below by hand (it is the same flow; the skills in `.claude/skills/` work in Cursor).

## The flow (what the script does, and what you do by hand)
1. Read: `gh issue view 123 --repo peptides-ai-ecosystem/web_scrape --comments`; write down the title, the acceptance criteria (one checkable line each) and the area. Stop and ask a person if the issue needs a secret, a production action or a decision.
2. Plan: read `AGENTS.md`, pick the skill in `.claude/skills/` whose description fits, list the files and ordered steps (one commit each). With `dryRun:true` the workflow stops here and returns the plan.
3. Implement: branch ticket/<n>-<slug> off origin/staging in its own worktree; follow the skill's numbered steps; one commit per step; add tests for new behaviour.
4. Verify: run `bash scripts/check.sh` from the unit folder and record the counts. On failure one fix round (code only, never the tests), then verify again; a second failure stops the run.
5. Review: two skeptics try to refute the change. One looks for changed behaviour (routes, JSON keys, status codes, migrations, XR contracts) and weakened or deleted tests; the other for pointers outside the unit, secrets and unmet acceptance criteria. Any refutation stops the run, nothing is published.
6. Publish: push the branch, open ONE PR to `staging` whose body lists each acceptance criterion with its evidence and the verify counts (it says `Refs #123`, not a closing keyword), and comment the PR link on the issue.

## Check in the PR
- Every acceptance criterion has evidence (a test name, a command line, a file), not a sentence.
- The diff holds no edited assertion, no `skip`, no new outside-the-unit pointer, no secret.
- `bash scripts/check.sh` is green in the PR and the commit trailers are the ones `AGENTS.md` asks for.
- You merge it, never the workflow.

## Never
Merge, target `main`/`master`, deploy, force-push, print or commit a secret, edit a test to make it pass, or change files outside this unit.

## Constants
The block at the top of the script (`REPO`, `CHECK`, `BASE`, `AREA`) is the only part that differs between units; the template lives in the ecosystem hub: https://github.com/peptides-ai-ecosystem/orchestrator/blob/staging/docs/ecosystem/workflow-template/README.md
