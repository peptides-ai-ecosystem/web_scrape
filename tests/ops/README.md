# tests/ops

Tests for the operational surface: operations/jobs API, health and commit sha, gateway token, Sentry capture and scrubbing, and what the Docker image must contain.

Marker: `ops` (`uv run pytest -m ops`).

Agent skills: `test_agent_skills.py` checks every skill's frontmatter, the Skills table, `docs/agents/skills.md` and that no steering file points outside the repo.
