"""The Docker image must ship Alembic, which creates this service's own tables.

The 29 Sep deploy left both competitor tables uncreated: `.dockerignore`
dropped every `*.sql` and the Dockerfile copied only the app, so the old boot
bootstrap failed with "No such file or directory". The tables are now an
Alembic revision, so the image needs `alembic.ini` and `alembic/`.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

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
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name, pattern.rstrip("/") + "/*"):
            ignored = not negate
    return ignored


def _revisions() -> list[Path]:
    return sorted((ROOT / "alembic" / "versions").glob("*.py"))


def test_alembic_files_exist_in_the_repo():
    assert (ROOT / "alembic.ini").is_file()
    assert (ROOT / "alembic" / "env.py").is_file()
    assert _revisions(), "no Alembic revision under alembic/versions/"


def test_alembic_files_are_not_excluded_from_the_build_context():
    for path in [ROOT / "alembic.ini", ROOT / "alembic" / "env.py", *_revisions()]:
        rel = path.relative_to(ROOT).as_posix()
        assert not _ignored(rel), f"{rel} is excluded by .dockerignore"


def test_dockerfile_copies_alembic_where_the_app_runs_it():
    # WORKDIR is /app; app/infrastructure/db/migrate.py resolves <app root>/alembic.ini.
    lines = [l.split() for l in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines() if l.startswith("COPY ")]
    assert ["COPY", "alembic.ini", "./"] in lines
    assert ["COPY", "alembic/", "./alembic/"] in lines
