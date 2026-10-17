"""Tests for the admin PK tab read endpoint ``GET /api/v1/pk/peptides`` (H18).

Offline: the DB pool is replaced by a fake, so no database is touched.
"""
from contextlib import contextmanager
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.v1.endpoints.graph as graph_endpoints
import app.services.graph_service as graph_service
from app.infrastructure.db.repositories.graph import (
    PK_SUMMARY_SQL,
    GraphRepository,
    pk_summary_row_to_dict,
)


def _row(**overrides):
    row = {
        "id": 12,
        "name": "BPC-157",
        "slug": "bpc-157",
        "methods": ["Oral", "Injectable", None],
        "curve_count": 8,
        "last_updated": datetime(2026, 10, 1, 3, 15),
        "headline_method": "Injectable",
        "half_life": "8 hrs",
        "peak_concentration": "48 min",
        "cleared_percentage": "~1.7 days",
        "action_type": "scraped",
    }
    row.update(overrides)
    return row


class TestRowShaping:
    def test_full_row(self):
        out = pk_summary_row_to_dict(_row())
        assert out == {
            "id": 12,
            "name": "BPC-157",
            "slug": "bpc-157",
            "source": "pep-pedia.org",
            "source_url": "https://pep-pedia.org/peptides/bpc-157",
            "methods": ["Injectable", "Oral"],
            "curve_count": 8,
            "last_updated": "2026-10-01T03:15:00",
            "action_type": "scraped",
            "headline": {
                "method": "Injectable",
                "half_life": "8 hrs",
                "peak": "48 min",
                "cleared": "~1.7 days",
            },
        }

    def test_missing_slug_has_no_source_url(self):
        out = pk_summary_row_to_dict(_row(slug="  "))
        assert out["slug"] is None
        assert out["source_url"] is None

    def test_empty_values_become_none(self):
        out = pk_summary_row_to_dict(
            _row(methods=None, curve_count=None, last_updated=None, half_life="", peak_concentration=None)
        )
        assert out["methods"] == []
        assert out["curve_count"] == 0
        assert out["last_updated"] is None
        assert out["headline"]["half_life"] is None
        assert out["headline"]["peak"] is None


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute(self, query, params=()):
        self.queries.append(query)

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows):
        self.cur = _FakeCursor(rows)

    def cursor(self):
        return self.cur


def test_repository_runs_summary_sql_and_shapes_rows():
    conn = _FakeConn([_row()])
    out = GraphRepository(conn).list_pk_summary()
    assert conn.cur.queries == [PK_SUMMARY_SQL]
    assert out[0]["source_url"] == "https://pep-pedia.org/peptides/bpc-157"


class _FakeDb:
    def __init__(self, graph):
        self.graph = graph


class _FakePool:
    def __init__(self, graph):
        self._db = _FakeDb(graph)

    @contextmanager
    def acquire(self):
        yield self._db


class _Graph:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error

    def list_pk_summary(self):
        if self.error:
            raise self.error
        return self.rows


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(graph_endpoints.router, prefix="/api/v1")
    return TestClient(app)


def test_endpoint_returns_count_and_peptides(client, monkeypatch):
    rows = [pk_summary_row_to_dict(_row())]
    monkeypatch.setattr(graph_service, "get_pool", lambda: _FakePool(_Graph(rows)))
    res = client.get("/api/v1/pk/peptides")
    assert res.status_code == 200
    assert res.json() == {"count": 1, "peptides": rows}


def test_endpoint_hides_db_error_detail(client, monkeypatch):
    graph = _Graph(error=RuntimeError("password=hunter2 connection refused"))
    monkeypatch.setattr(graph_service, "get_pool", lambda: _FakePool(graph))
    res = client.get("/api/v1/pk/peptides")
    assert res.status_code == 500
    assert "hunter2" not in res.text


def test_route_is_behind_gateway_auth():
    from app.api.v1.routers import api_router

    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/pk/peptides" in paths
