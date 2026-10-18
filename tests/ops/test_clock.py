"""utc_now_naive replaces datetime.utcnow (ADR 0010): same naive-UTC value, no deprecated call left."""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.clock import utc_now_naive

ROOT = Path(__file__).resolve().parents[2]


def test_utc_now_naive_is_naive_utc():
    before = datetime.now(timezone.utc).replace(tzinfo=None)
    value = utc_now_naive()
    after = datetime.now(timezone.utc).replace(tzinfo=None)
    assert value.tzinfo is None
    assert before <= value <= after
    assert "+" not in value.isoformat()


def test_timestamp_matches_what_utcnow_gave():
    # utcnow().timestamp() reads the naive UTC value as local time; the helper keeps that.
    assert abs(utc_now_naive().timestamp() - time.mktime(time.gmtime())) < 5


def test_no_deprecated_utcnow_call_remains():
    needle = "datetime." + "utcnow"  # fragments, so this file does not match itself
    result = subprocess.run(
        ["git", "grep", "-n", "-e", needle, "--", "app", "scripts", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout
