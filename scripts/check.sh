#!/usr/bin/env bash
# Local quality gate (and what .github/workflows/ci.yml runs): the offline test
# suite. No linter or type checker is configured in this repo.
# `uv run pytest` and this script select the same tests.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --frozen

uv run pytest -q "$@"
