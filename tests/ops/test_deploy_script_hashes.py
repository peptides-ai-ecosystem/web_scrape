"""The three `.deploy/*.sh` scripts are shared by every microservice repo.

`docs/ops/deploy.md` records their sha256 (line endings normalised to
LF). Changing a script without updating the table fails here, so a drift
between repos is a deliberate, visible edit. The cross-repo comparison itself
is `scripts/ecosystem/check-shared-deploy.sh` in the orchestrator checkout.
"""

import hashlib
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ops

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "ops" / "deploy.md"
SCRIPTS = ("staging-deploy.sh", "staging-gate.sh", "staging-remote.sh")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _recorded() -> dict[str, str]:
    return dict(re.findall(r"`(staging-[a-z]+\.sh)`\s*\|\s*`([0-9a-f]{64})`", DOC.read_text(encoding="utf-8")))


@pytest.mark.parametrize("script", SCRIPTS)
def test_recorded_hash_matches_the_script(script: str) -> None:
    recorded = _recorded()
    assert script in recorded, f"docs/ops/deploy.md has no recorded sha256 for {script}"
    assert recorded[script] == _sha256(ROOT / ".deploy" / script), (
        f".deploy/{script} changed: update its sha256 in docs/ops/deploy.md and the same script in every "
        "microservice repo (XR-11)"
    )
