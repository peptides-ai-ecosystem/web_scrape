# main.py has been removed.
# Use the FastAPI server (api_server.py) instead:
#   uv run api_server.py
#
# Available endpoints:
#   POST /api/v1/sync/core        — scrape + core DB sync
#   POST /api/v1/sync/graph       — scrape + graph DB sync
#   POST /api/v1/sync/graph-missing — scrape + graph DB sync (missing only)
#   POST /api/v1/evaluation/core  — core evaluation
#   POST /api/v1/evaluation/graph — graph evaluation
#
# Or run via CLI with uv:
#   uv run python -c "from src.api.v1.scripts import sync_core; sync_core()"  # (if such scripts exist)
