# Workflow: fix a bug

1. Reproduce it offline. Pick the seam: an extractor or service with a recorded page (`tests/vendors/fixtures/`), a mapper group (`tests/sync/`), or an endpoint through the test client.
2. Write the failing test there before touching the code, and run it to see it fail for the reason in the report.
3. If the symptom matches `docs/agents/troubleshooting.md`, follow that row first; skill `debugging-a-scrape` covers 401s, gateway 502, missing columns and vendor failures.
4. Fix at the layer that owns the behaviour (a SQL fix is in `app/repositories/`, never in an endpoint).
5. A fix that needs a platform column or type change is not a fix here: open an `[XR-8]` issue in peptides-platform (`docs/agents/workflows/schema-change.md`).
6. Keep the test. If an agent made the mistake, add one line to `CODING_STANDARDS.md`.

Verify: the new test fails without the fix and passes with it; `scripts/check.sh` passes; no baseline entry grew.
