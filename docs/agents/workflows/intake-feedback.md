# Turn feedback into tickets (workflow `intake-feedback`)

The script `.claude/workflows/intake-feedback.js` takes the text you add in the Google doc (or any review text) and files one GitHub issue per deliverable in peptides-ai-ecosystem/web_scrape. It only creates issues; it does not change code.

## Start it
- Claude Code: `Workflow({name:'intake-feedback', args:{text:'<pasted feedback>', source:'<doc link or label>'}})`. Add `run:true` to also run `run-ticket` for every new issue, one after the other (see `docs/agents/workflows/run-ticket.md`).
- Cursor: not runnable there; open a terminal here and start Claude Code, or do the checklist by hand.

## The flow
1. Split: one item per deliverable (something one PR can deliver), each with id, title, why, acceptance lines and area. Items that belong to another repo are skipped and listed so you can file them there.
2. Dedupe: `gh issue list --repo peptides-ai-ecosystem/web_scrape --state open --limit 200`; an item already covered by an open issue is not filed again (the script reports the existing number).
3. Create: one issue per new item following `docs/agents/issue-tracker.md` and the labels in `docs/agents/triage-labels.md`. Body sections in this order: Summary, Why, What to do, Acceptance, Out of scope, References (with the source link and the item id).
4. Run (only with `run:true`): `run-ticket` for each new issue, sequentially.

## Check afterwards
- The new issues read like the template and each Acceptance line is checkable.
- Nothing was filed twice; out-of-repo items were handed to the right repo.
- Nothing secret was pasted into an issue.

## Never
Merge, touch `main`/`master`, deploy, print a secret, or edit code.
