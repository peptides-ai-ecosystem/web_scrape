#!/usr/bin/env bash
# Local quality gate (and what .github/workflows/ci.yml runs): the offline test
# suite. No linter or type checker is configured in this repo.
#
# Deselected: failures that already exist on origin/staging, kept visible here
# until they are fixed (each is a broken test, not a broken feature):
#   - test_actual_ingestion: a manual script (argparse, needs a real DB and CSV)
#     that pytest collects; its `db_url` fixture does not exist.
#   - test_health_route_registered: imports `web_scrape.main`, a package name
#     that does not exist (the app is `main`).
#   - test_scrape_current_view_mock: calls GraphExtractor._scrape_current_view
#     without the `time_range` argument the method now requires.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --frozen

uv run pytest -q -p no:cacheprovider \
  --deselect app/tests/test_actual_ingestion.py::test_actual_ingestion \
  --deselect app/tests/test_graph_extractor.py::test_scrape_current_view_mock \
  "$@"
