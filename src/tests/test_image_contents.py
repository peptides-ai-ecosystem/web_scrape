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
        assert path.parent == ROOT / "migrations", path
        assert path.is_file(), path


def test_schema_files_are_not_excluded_from_the_build_context():
    for path in VENDOR_SCHEMA_FILES:
        rel = path.relative_to(ROOT).as_posix()
        assert not _ignored(rel), f"{rel} is excluded by .dockerignore"


def test_dockerfile_copies_the_schema_files_where_vendor_schema_reads_them():
    # WORKDIR is /app; vendor_schema.py resolves <app root>/migrations/<file>.
    copies = [
        line.split() for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("COPY migrations/")
    ]
    assert copies, "Dockerfile does not COPY anything from migrations/"
    for path in VENDOR_SCHEMA_FILES:
        rel = path.relative_to(ROOT).as_posix()
        assert any(rel in c[1:-1] and c[-1] == "./migrations/" for c in copies), (
            f"Dockerfile does not COPY {rel} into ./migrations/"
        )
