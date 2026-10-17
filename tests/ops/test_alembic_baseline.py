"""The Alembic baseline (decision R10) against a throwaway Docker Postgres.

* an empty database gets both tables and ``alembic_version_web_scrape``;
* a database where the tables already exist (staging, production) upgrades in
  place: nothing is dropped or changed, only the version row is added;
* a platform table in the same database is never touched;
* the models mirror the revision (``alembic check`` finds no difference).

Skipped without a Docker daemon (marker ``docker``). Never uses a URL from ``.env``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OWN = {"vendor_scrape_targets", "vendor_price_observations"}

pytestmark = pytest.mark.docker


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture(scope="module")
def pg_url():
    external = os.environ.get("WEB_SCRAPE_TEST_PG_URL")
    if external:  # a throwaway Postgres the operator started; never a real database
        yield external
        return
    if not _docker_ok():
        pytest.skip("needs a local Docker daemon")
    name = f"ws-alembic-{uuid.uuid4().hex[:8]}"
    out = subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD=pw", "-p", "127.0.0.1::5432", "postgres:17"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        pytest.skip(f"cannot start postgres: {out.stderr[-200:]}")
    try:
        port = subprocess.run(["docker", "port", name, "5432/tcp"], capture_output=True, text=True).stdout.strip().rsplit(":", 1)[1]
        url = f"postgresql://postgres:pw@127.0.0.1:{port}/postgres"
        import psycopg2

        for _ in range(180):
            try:
                psycopg2.connect(url, connect_timeout=2).close()
                break
            except Exception:
                time.sleep(1)
        else:
            pytest.skip("postgres did not become ready")
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url, "LOG_DIR": str(ROOT / "log")}
    return subprocess.run(["uv", "run", "--no-sync", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True)


def _tables(url: str) -> set[str]:
    import psycopg2

    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("select table_name from information_schema.tables where table_schema='public'")
        return {r[0] for r in cur.fetchall()}


def _exec(url: str, sql: str):
    import psycopg2

    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute(sql)


def _reset(url: str):
    _exec(url, "drop schema public cascade; create schema public")


def test_empty_database_gets_both_tables_and_the_version_table(pg_url):
    _reset(pg_url)
    res = _alembic(pg_url, "upgrade", "head")
    assert res.returncode == 0, res.stderr[-1500:]
    assert OWN | {"alembic_version_web_scrape"} <= _tables(pg_url)
    # a second run is a no-op
    assert _alembic(pg_url, "upgrade", "head").returncode == 0


def test_existing_tables_upgrade_in_place_and_keep_their_rows(pg_url):
    _reset(pg_url)
    assert _alembic(pg_url, "upgrade", "head").returncode == 0
    _exec(pg_url, "insert into vendor_scrape_targets (slug, name) values ('rival', 'Rival')")
    _exec(pg_url, "drop table alembic_version_web_scrape")  # the pre-Alembic state of staging/production
    res = _alembic(pg_url, "upgrade", "head")
    assert res.returncode == 0, res.stderr[-1500:]
    import psycopg2

    with psycopg2.connect(pg_url) as conn, conn.cursor() as cur:
        cur.execute("select slug from vendor_scrape_targets")
        assert cur.fetchall() == [("rival",)]
        cur.execute("select version_num from alembic_version_web_scrape")
        assert cur.fetchall() == [("4b1d0c2e9f10",)]


def test_platform_tables_are_not_touched(pg_url):
    _reset(pg_url)
    _exec(pg_url, "create table peptides (id serial primary key, name text); insert into peptides (name) values ('BPC-157')")
    _exec(pg_url, "create table alembic_version (version_num varchar(32) not null)")
    assert _alembic(pg_url, "upgrade", "head").returncode == 0
    import psycopg2

    with psycopg2.connect(pg_url) as conn, conn.cursor() as cur:
        cur.execute("select name from peptides")
        assert cur.fetchall() == [("BPC-157",)]
        cur.execute("select count(*) from alembic_version")
        assert cur.fetchone() == (0,)
    assert _alembic(pg_url, "downgrade", "base").returncode == 0
    assert "peptides" in _tables(pg_url)


def test_models_mirror_the_revision(pg_url):
    _reset(pg_url)
    assert _alembic(pg_url, "upgrade", "head").returncode == 0
    res = _alembic(pg_url, "check")
    assert res.returncode == 0, res.stdout[-1500:] + res.stderr[-1500:]
