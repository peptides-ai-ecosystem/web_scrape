# Issue tracker (web_scrape)

Issues, specs and tickets are GitHub issues on `peptides-ai-ecosystem/web_scrape`, managed with the `gh` CLI (or the REST API when `gh` is not installed).

- Create: `gh issue create --repo peptides-ai-ecosystem/web_scrape --title "<title>" --body-file <file>`.
- Cross-repo work is its own issue in the owning repo, titled with the contract: `[XR-8] ...` in peptides-platform for a missing column, `[XR-14] ...` here for an API the platform or peptide calls.
- Branches come off `staging`; `master` is production and only changes on "release to production". A PR targets `staging`.
- Close an issue when the change is verified on staging, not when it is only on a branch.
