"""scripts/ops/sync_supabase.sh restores a dump over its target; it must refuse a non-staging host."""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "sync_supabase.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")


def _run(target, **env):
    return subprocess.run(
        [BASH, str(SCRIPT), "postgres://u:p@src.example:5432/db", target],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **env},
    )


def test_refuses_a_target_without_staging_in_the_host():
    res = _run("postgres://u:secret@db.prod.example:5432/db")
    assert res.returncode == 2
    assert "does not contain 'staging'" in res.stderr
    assert "secret" not in res.stderr + res.stdout


def test_override_is_required_for_a_non_staging_target():
    res = _run("postgres://u:p@db.example:5432/db", I_KNOW_THIS_IS_PRODUCTION="1")
    # Passes the guard, then fails at pg_dump (not installed or unreachable): never exit code 2.
    assert res.returncode != 2
