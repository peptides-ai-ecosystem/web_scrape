"""Status mapping of the graph and core-data endpoints after the service split.

Offline: the pool is a fake, so no database is touched. Each case pins the
status code and ``detail`` the endpoint returned before the logic moved into
``graph_service`` / ``core_data_service``.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.services.core_data_service as core_data_service
import app.services.graph_service as graph_service
from app.api.v1.endpoints import core, graph


class _Graph:
    def __init__(self, methods=None, data=None):
        self.methods = methods or []
        self.data = data

    def get_methods_for_peptide(self, peptide_id):
        return self.methods

    def get_visualization_data(self, peptide_id, method):
        return self.data


class _Peptides:
    def __init__(self, row=None):
        self.row = row

    def get_by_id(self, peptide_id):
        return self.row

    def get_by_slug(self, slug):
        return self.row


class _Inspector:
    def fetch_payload(self, peptide):
        return {"peptide": peptide, "benefits": []}

    def lookups(self):
        return {"benefits": [{"id": 1, "name": "x"}]}

    def list_peptides(self, q=None):
        return [{"id": 1, "name": "BPC-157", "q": q}]


def _pool(**db):
    ns = SimpleNamespace(graph=_Graph(), peptide=_Peptides(), inspector=_Inspector())
    for k, v in db.items():
        setattr(ns, k, v)

    class Pool:
        @contextmanager
        def acquire(self):
            yield ns

    return Pool()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(graph.router, prefix="/api/v1")
    app.include_router(core.router, prefix="/api/v1/core")
    return TestClient(app)


def _use(monkeypatch, pool):
    monkeypatch.setattr(graph_service, "get_pool", lambda: pool)
    monkeypatch.setattr(core_data_service, "get_pool", lambda: pool)


def test_methods_404_when_peptide_has_no_graph(client, monkeypatch):
    _use(monkeypatch, _pool())
    res = client.get("/api/v1/peptide/7/methods")
    assert res.status_code == 404
    assert res.json()["detail"].startswith("No graph data found for peptide ID 7.")


def test_graph_422_for_unknown_method(client, monkeypatch):
    _use(monkeypatch, _pool(graph=_Graph(methods=[{"id": 1, "name": "Oral"}])))
    res = client.get("/api/v1/graph/7", params={"method": "Nasal"})
    assert res.status_code == 422
    assert res.json()["detail"] == "Invalid method 'Nasal' for peptide 7. Valid methods: Oral"


def test_graph_matches_method_case_insensitively(client, monkeypatch):
    data = {"peptide_name": "X", "administration_method": "Oral", "24h": {}}
    _use(monkeypatch, _pool(graph=_Graph(methods=[{"id": 1, "name": "Oral"}], data=data)))
    res = client.get("/api/v1/graph/7", params={"method": "oral"})
    assert res.status_code == 200
    assert res.json() == data


def test_graph_404_when_no_time_ranges(client, monkeypatch):
    data = {"peptide_name": "X", "administration_method": "Oral"}
    _use(monkeypatch, _pool(graph=_Graph(methods=[{"id": 1, "name": "Oral"}], data=data)))
    res = client.get("/api/v1/graph/7", params={"method": "Oral"})
    assert res.status_code == 404


def test_graph_500_on_db_error(client, monkeypatch):
    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(graph_service, "get_pool", boom)
    res = client.get("/api/v1/peptides")
    assert res.status_code == 500
    assert res.json()["detail"] == "Failed to fetch peptides: db down"


def test_core_peptide_404(client, monkeypatch):
    _use(monkeypatch, _pool())
    res = client.get("/api/v1/core/peptide/3")
    assert res.status_code == 404
    assert res.json()["detail"] == "Peptide ID 3 not found"
    res = client.get("/api/v1/core/peptide/by-slug/nope")
    assert res.json()["detail"] == "Peptide slug 'nope' not found"


def test_core_peptide_payload_and_lookups(client, monkeypatch):
    _use(monkeypatch, _pool(peptide=_Peptides(row={"id": 3, "name": "X"})))
    assert client.get("/api/v1/core/peptide/3").json() == {"peptide": {"id": 3, "name": "X"}, "benefits": []}
    assert client.get("/api/v1/core/lookups").json() == {"benefits": [{"id": 1, "name": "x"}]}
    assert client.get("/api/v1/core/peptides", params={"q": "bpc"}).json()[0]["q"] == "bpc"
