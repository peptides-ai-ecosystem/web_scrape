"""The Docker image must ship every SQL file the service applies on boot.

The 29 Sep deploy left both competitor tables uncreated: `.dockerignore`
dropped every `*.sql` and the Dockerfile copied only `src/` and `main.py`, so
`ensure_vendor_schema` failed with "No such file or directory" at startup.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

from src.infrastructure.db.vendor_schema import VENDOR_SCHEMA_FILES

ROOT = Path(__file__).resolve().parents[2]


def _ignored(name: str) -> bool:
    """Apply .dockerignore's patterns in order (later lines win, ``!`` re-includes)."""
    ignored = False
    for raw in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        pattern = line[1:] if negate else line
        if fnmatch.fnmatch(name, pattern):
            ignored = not negate
    return ignored


def test_schema_files_exist_in_the_repo():
    for path in VENDOR_SCHEMA_FILES:
        assert path.is_file(), path


def test_schema_files_are_not_excluded_from_the_build_context():
    for path in VENDOR_SCHEMA_FILES:
        assert not _ignored(path.name), f"{path.name} is excluded by .dockerignore"


def test_dockerfile_copies_the_schema_files_next_to_main():
    copies = " ".join(
        line for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("COPY")
    )
    for path in VENDOR_SCHEMA_FILES:
        assert path.name in copies, f"Dockerfile does not COPY {path.name}"
