"""The agent skills must be usable on their own.

Fails when a skill has no or invalid frontmatter, ``name`` differs from its
folder, the description does not start with a trigger ("Use when ..."), a skill
folder has no SKILL.md, a steering file, workflow or skill points outside this
repo (``../``, a sibling repo path) or names a path that does not exist, a
skill is missing from the AGENTS.md Skills table or ``docs/agents/skills.md``,
AGENTS.md is longer than 45 lines, or CLAUDE.md is not ``@AGENTS.md``.
Standard library only.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.ops

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".claude" / "skills"
OWN_NAME = "web_scrape"

SIBLINGS = {
    "orchestrator",
    "peptides-platform",
    "chat-microservice",
    "admin-microservice",
    "analytics-microservice",
    "peptide-microservice",
    "sds-microservice",
    "web_scrape",
    "peptide-calculator",
    "peptide_web_sync",
    "apps",
    "packages",
} - {OWN_NAME}

KNOWN_DIRS = {
    "app",
    "docs",
    "scripts",
    "tests",
    "alembic",
    "migrations",
    "config",
    "contracts",
    "deploy",
    "src",
    "store",
    ".claude",
    ".github",
    ".maestro",
    ".eas",
}
FILE_EXT = (".py", ".md", ".sh", ".yml", ".yaml", ".json", ".ts", ".tsx", ".js", ".sql", ".toml", ".ini")
MARKERS = ("mcp:", "sdk:", "external:")
NOT_COMMITTED = {"config/vendor_targets.json"}  # deployment config, deliberately not committed
LINK_TEXT = re.compile(r"\[[^\]]*\]\(https?://[^)]*\)")
BACKTICK = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
OUTSIDE = re.compile(r"(?<![\w.])\.\./[\w.]")
DRIVE_PATH = re.compile(r"(?<![\w/])[A-Za-z]:[\\/](?!/)")
TRIGGER = re.compile(r"^Use (when|before|to)\b")


def _skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS.iterdir() if p.is_dir()) if SKILLS.is_dir() else []


def _docs() -> list[Path]:
    found: set[Path] = set()
    patterns = (
        "AGENTS.md",
        "CLAUDE.md",
        "CODING_STANDARDS.md",
        "GLOSSARY.md",
        "docs/agents/**/*.md",
        ".claude/skills/**/*.md",
    )
    for pattern in patterns:
        found.update(p for p in ROOT.glob(pattern) if p.is_file())
    return sorted(found)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _frontmatter(skill: Path) -> dict[str, str]:
    lines = (skill / "SKILL.md").read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", "SKILL.md must start with ---"
    end = lines.index("---", 1) if "---" in lines[1:] else -1
    assert end > 0, "frontmatter is not closed with ---"
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta


def _exists(token: str, doc: Path) -> bool:
    if token in NOT_COMMITTED:
        return True
    if "*" in token:
        return any(ROOT.glob(token)) or any(doc.parent.glob(token))
    return (ROOT / token).exists() or (doc.parent / token).exists()


def test_there_are_skills():
    assert _skill_dirs(), ".claude/skills has no skill folders"


@pytest.mark.parametrize("skill", _skill_dirs(), ids=lambda p: p.name)
def test_skill_frontmatter(skill: Path):
    assert (skill / "SKILL.md").is_file(), f"{skill.name} has no SKILL.md"
    meta = _frontmatter(skill)
    assert meta.get("name") == skill.name, f"name {meta.get('name')!r} != folder {skill.name!r}"
    description = meta.get("description", "")
    assert TRIGGER.match(description), f"description must start with 'Use when ...': {description[:60]!r}"
    assert len(description) >= 60, "description is too short to auto-trigger"
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"^1\. ", body, re.M), "body needs numbered steps"


def test_agents_md_is_short_and_lists_every_skill():
    lines = (ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 45, f"AGENTS.md has {len(lines)} lines (max 45)"
    rows = [ln for ln in lines if ln.startswith("|")]
    has_header = any("Skill" in ln and "Use when" in ln for ln in rows)
    assert has_header, "AGENTS.md needs a Skills table (| Skill | Use when |)"
    for skill in _skill_dirs():
        assert any(f"`{skill.name}`" in ln for ln in rows), f"{skill.name} is not in the AGENTS.md Skills table"


def test_claude_md_imports_agents_md():
    assert (ROOT / "CLAUDE.md").read_text(encoding="utf-8").strip() == "@AGENTS.md"


def test_skills_page_lists_every_skill():
    page = ROOT / "docs" / "agents" / "skills.md"
    assert page.is_file(), "docs/agents/skills.md is missing"
    text = page.read_text(encoding="utf-8")
    for skill in _skill_dirs():
        assert f"`{skill.name}`" in text, f"{skill.name} is not on docs/agents/skills.md"


@pytest.mark.parametrize("doc", _docs(), ids=_rel)
def test_no_pointer_leaves_the_repo_and_every_path_exists(doc: Path):
    text = doc.read_text(encoding="utf-8")
    problems: list[str] = []
    if DRIVE_PATH.search(LINK_TEXT.sub("", text)):
        problems.append("names a drive path such as C: or G: (machine specific); say what to do instead")
    if OUTSIDE.search(text):
        problems.append("points outside the repo with ../ (use a GitHub URL)")
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#")[0]
        if path.startswith("../") or (path and not (doc.parent / path).exists()):
            problems.append(f"link ({target}) is outside or does not resolve")
    for span in BACKTICK.findall(LINK_TEXT.sub("", text)):
        if "://" in span or span.startswith(MARKERS):
            continue
        for raw in span.split():
            token = re.split(r"#|::", raw.rstrip(".,;:)"))[0]
            token = re.sub(r":\d+(-\d+)?$", "", token).lstrip("(")
            placeholder = any(ch in token for ch in "<>$={}|*") or "..." in token
            if not token or placeholder or token.startswith(("-", "/", "~", "./")):
                continue
            first = token.split("/")[0]
            if "/" in token and first in SIBLINGS:
                problems.append(f"`{token}` is in another repo (use a GitHub URL)")
            elif "/" in token and (first in KNOWN_DIRS or (ROOT / first).is_dir() or token.endswith(FILE_EXT)):
                if not _exists(token.rstrip("/"), doc):
                    problems.append(f"`{token}` does not exist")
    assert not problems, f"{_rel(doc)}: " + "; ".join(sorted(set(problems)))


# --- Claude workflows (.claude/workflows) ----------------------------------------------------
WORKFLOWS = ROOT / ".claude" / "workflows"
WORKFLOW_NAMES = ("run-ticket", "intake-feedback")
WORKFLOW_FORBIDDEN = ("gh pr merge", "git push origin main", "--force", "Date.now", "Math.random", "new Date()")
CONST_RE = {key: re.compile(rf"^const {key} = '([^']*)'", re.M) for key in ("REPO", "CHECK", "BASE", "AREA")}


def _workflow_files() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.js")) if WORKFLOWS.is_dir() else []


def test_both_workflows_and_their_pages_exist():
    for name in WORKFLOW_NAMES:
        assert (WORKFLOWS / f"{name}.js").is_file(), f".claude/workflows/{name}.js is missing"
        assert (ROOT / "docs" / "agents" / "workflows" / f"{name}.md").is_file(), f"docs/agents/workflows/{name}.md is missing"


@pytest.mark.parametrize("wf", _workflow_files(), ids=lambda p: p.name)
def test_workflow_meta_constants_and_guardrails(wf: Path):
    text = wf.read_text(encoding="utf-8")
    assert text.lstrip().startswith("export const meta = {"), "must start with `export const meta` (a literal)"
    name = re.search(r"^\s+name: '([^']+)'", text, re.M)
    assert name and name.group(1) == wf.stem, "meta.name must equal the file name"
    assert "// ---- CONSTANTS" in text and "// ---- END CONSTANTS ----" in text
    consts = {key: pat.search(text) for key, pat in CONST_RE.items()}
    assert all(consts.values()), f"constants block incomplete: {[k for k, v in consts.items() if not v]}"
    assert consts["REPO"].group(1) != "OWNER/REPO", "REPO constant not filled in"
    assert consts["BASE"].group(1) == "staging"
    assert "../" not in text, "a workflow may only point inside its unit"
    for bad in WORKFLOW_FORBIDDEN:
        assert bad not in text, f"workflow must not contain {bad!r}"


def test_workflows_share_their_constants():
    found = {
        key: {CONST_RE[key].search(p.read_text(encoding="utf-8")).group(1) for p in _workflow_files()}
        for key in ("REPO", "CHECK", "AREA")
    }
    assert all(len(v) == 1 for v in found.values()), f"run-ticket and intake-feedback disagree: {found}"


@pytest.mark.parametrize("wf", _workflow_files(), ids=lambda p: p.name)
def test_workflow_syntax(wf: Path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the syntax check needs `node --check`")
    body = wf.read_text(encoding="utf-8").replace("export const meta", "const meta", 1)
    wrapped = f"(async function (agent, pipeline, parallel, phase, log, workflow, args, budget) {{\n{body}\n}})\n"
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / f"{wf.stem}.mjs"
        target.write_text(wrapped, encoding="utf-8")
        result = subprocess.run([node, "--check", str(target)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_agents_md_names_existing_workflows():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for name in WORKFLOW_NAMES:
        assert f".claude/workflows/{name}.js" in text, f"AGENTS.md does not name the {name} workflow"
    for listed in re.findall(r"\.claude/workflows/([\w-]+\.js)", text):
        assert (WORKFLOWS / listed).is_file(), f"AGENTS.md names {listed}, which does not exist"
