"""Run mypy and compare against the recorded baseline (a ratchet).

The baseline (``scripts/mypy-baseline.txt``) lists the errors that existed when
the gate was added, one per line as ``path: [code] message`` (line numbers are
left out so unrelated edits do not churn it). The gate fails on any error that is
not in the baseline (or that appears more often than recorded) and tells you when
baseline entries have been fixed, so they can be removed.

    uv run python scripts/mypy_ratchet.py            # check
    uv run python scripts/mypy_ratchet.py --update   # re-record (only after fixing, never to hide new errors)
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "mypy-baseline.txt"
LINE = re.compile(r"^(?P<path>[^:]+):\d+(?::\d+)?: error: (?P<msg>.*?)(?:\s+\[(?P<code>[\w-]+)\])?$")


def run_mypy() -> Counter[str]:
    proc = subprocess.run([sys.executable, "-m", "mypy"], cwd=ROOT, capture_output=True, text=True, check=False)
    found: Counter[str] = Counter()
    for raw in proc.stdout.splitlines():
        match = LINE.match(raw.strip())
        if match:
            path = match["path"].replace("\\", "/")
            found[f"{path}: [{match['code'] or '-'}] {match['msg']}"] += 1
    if proc.returncode not in (0, 1):  # 2 = mypy itself failed
        print(proc.stdout + proc.stderr)
        raise SystemExit(proc.returncode)
    return found


def read_baseline() -> Counter[str]:
    if not BASELINE.exists():
        return Counter()
    lines = [ln for ln in BASELINE.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
    return Counter(lines)


def main() -> int:
    found = run_mypy()
    if "--update" in sys.argv:
        header = (
            "# mypy baseline; shrink it, never grow it. Regenerate: uv run python scripts/mypy_ratchet.py --update\n"
        )
        body = "".join(f"{key}\n" for key in sorted(found.elements()))
        BASELINE.write_text(header + body, encoding="utf-8", newline="\n")
        print(f"mypy baseline recorded: {sum(found.values())} errors")
        return 0
    baseline = read_baseline()
    new = found - baseline
    fixed = baseline - found
    if new:
        print("mypy: errors not in the baseline (fix them):")
        for key in sorted(new.elements()):
            print(f"  {key}")
    if fixed:
        print(f"mypy: {sum(fixed.values())} baseline error(s) are fixed; run --update to shrink the baseline.")
    print(f"mypy: {sum(found.values())} errors, baseline {sum(baseline.values())}, new {sum(new.values())}")
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
