"""Write the platform-schema snapshot the contract test runs against in CI (XR-8).

Reads the Drizzle schema from a peptides-platform checkout (default
``PLATFORM_SCHEMA_REPO`` or the workspace checkout), keeps only the tables this
service queries, writes or deletes from, and saves their columns as
``contracts/platform-schema/<date>.json`` (older snapshots are removed).

    uv run python scripts/export_platform_schema.py [--repo PATH]

Run it from a platform checkout on ``staging`` whenever the platform schema or
this service's SQL changes, and commit the result. The contract test fails when
a checkout is present and the snapshot no longer matches it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    return out.stdout.strip()


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from tests.sync.platform_schema import PLATFORM_REPO, SNAPSHOT_DIR, parse_drizzle_schema, tables_in_use

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=PLATFORM_REPO)
    args = parser.parse_args()
    schema = parse_drizzle_schema(args.repo)
    used = tables_in_use()
    missing = sorted(used - set(schema))
    if missing:
        print(f"warning: tables used here but not declared by the platform: {missing}")
    payload = {
        "source": {
            "repo": "peptides-ai-ecosystem/peptides-platform",
            "branch": _git(args.repo, "branch", "--show-current") or None,
            "commit": _git(args.repo, "rev-parse", "HEAD") or None,
        },
        "generated_at": date.today().isoformat(),
        "generator": "scripts/export_platform_schema.py",
        "tables": {t: sorted(schema[t]) for t in sorted(used) if t in schema},
    }
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for old in SNAPSHOT_DIR.glob("*.json"):
        old.unlink()
    target = SNAPSHOT_DIR / f"{payload['generated_at']}.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {target.relative_to(ROOT)}: {len(payload['tables'])} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
