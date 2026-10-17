#!/usr/bin/env bash
# Local quality gate (and what .github/workflows/ci.yml runs): ruff lint, ruff
# format, the mypy ratchet and the offline test suite.
# Lint debt that predates the gate is recorded in [tool.ruff.lint.per-file-ignores]
# (pyproject.toml) and scripts/mypy-baseline.txt: both may only shrink.
# `uv run pytest` and this script select the same tests.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --frozen

uv run ruff check .
uv run ruff format --check .
uv run python scripts/mypy_ratchet.py

uv run pytest -q "$@"
