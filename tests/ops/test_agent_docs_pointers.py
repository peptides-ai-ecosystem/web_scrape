"""Agent-facing docs must not point at paths that do not exist.

A moved file with a stale pointer in AGENTS.md, a skill or a workflow sends the
next agent to nothing. This test reads every steering doc and fails when

* a backticked path under one of this repo's top-level folders does not exist,
* a relative markdown link does not resolve, or
* a doc points at a sibling checkout (``../orchestrator`` and friends): other
  repos are referenced by GitHub URL, because a checkout may not be there.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

TOP_DIRS = (
    "app/",
    "docs/",
    "scripts/",
    "tests/",
    "alembic/",
    "migrations/",
    "config/",
    "contracts/",
    ".claude/",
    ".github/",
)

# Deployment config that is deliberately not committed.
NOT_COMMITTED = {"config/vendor_targets.json"}

DOC_GLOBS = [
    "AGENTS.md",
    "CLAUDE.md",
    "CODING_STANDARDS.md",
    "GLOSSARY.md",
    "README.md",
    "docs/README.md",
    "docs/adding-a-scraper.md",
    "docs/agents/**/*.md",
    "docs/adr/*.md",
    "docs/ops/*.md",
    "docs/product/*.md",
    ".claude/skills/*/SKILL.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "tests/README.md",
    "tests/*/README.md",
    "migrations/README.md",
]

SIBLING_POINTER = re.compile(
    r"\.\./(?:orchestrator|peptides-platform|chat-microservice|admin-microservice|analytics-microservice|"
    r"peptide-microservice|sds-microservice|peptide-calculator|peptide_web_sync)"
)
BACKTICK = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _docs() -> list[Path]:
    found: set[Path] = set()
    for pattern in DOC_GLOBS:
        found.update(p for p in ROOT.glob(pattern) if p.is_file())
    return sorted(found)


def _candidate(span: str) -> str | None:
    token = span.strip().split()[0] if span.strip() else ""
    token = token.rstrip(".,;:)")
    token = re.split(r"::|#", token)[0]
    token = re.sub(r":\d+(-\d+)?$", "", token)
    if not token.startswith(TOP_DIRS):
        return None
    if any(ch in token for ch in "<>$={}()|") or "..." in token or token.startswith(("http", "--")):
        return None
    return token.rstrip("/")


def _exists(token: str) -> bool:
    if token in NOT_COMMITTED:
        return True
    if "*" in token:
        return any(ROOT.glob(token))
    return (ROOT / token).exists()


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_the_steering_docs_exist():
    names = {_rel(p) for p in _docs()}
    for required in ("AGENTS.md", "CODING_STANDARDS.md", "GLOSSARY.md", "docs/agents/commands.md"):
        assert required in names, f"{required} is missing"


def test_agents_md_stays_a_pointer_file():
    lines = (ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 45, f"AGENTS.md has {len(lines)} lines; move detail into docs/agents/"


@pytest.mark.parametrize("doc", _docs(), ids=_rel)
def test_doc_pointers_resolve(doc: Path):
    text = doc.read_text(encoding="utf-8")
    problems: list[str] = []

    for match in SIBLING_POINTER.finditer(text):
        problems.append(f"points at a sibling checkout: {match.group(0)} (use a GitHub URL)")

    for span in BACKTICK.findall(text):
        token = _candidate(span)
        if token and not _exists(token):
            problems.append(f"`{token}` does not exist")

    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#")[0]
        if path and not (doc.parent / path).exists():
            problems.append(f"link ({target}) does not resolve")

    assert not problems, f"{_rel(doc)}: " + "; ".join(sorted(set(problems)))
