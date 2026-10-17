"""``/api/v1/evaluation`` routes: the body is validated, then ``evaluation_service`` queues the job."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.services.evaluation_service as svc
from app.api.v1.endpoints import evaluation


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(evaluation.router, prefix="/api/v1/evaluation")
    return TestClient(app)


def test_missing_database_url_is_500(client, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    res = client.post("/api/v1/evaluation/core", json={"limit": 1})
    assert res.status_code == 500
    assert res.json()["detail"] == "DATABASE_URL not configured."


def test_missing_csv_is_500(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setattr(svc, "GRAPH_CSV", tmp_path / "graph.csv")
    res = client.post("/api/v1/evaluation/graph", json={})
    assert res.status_code == 500
    assert res.json()["detail"] == f"Graph CSV not found at {tmp_path / 'graph.csv'}. Run a graph sync first."


def test_accepted_job_runs_the_task(client, monkeypatch, tmp_path):
    csv_path = tmp_path / "enhanced.csv"
    csv_path.write_text("Peptide_Name\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setattr(svc, "ENHANCED_CSV", csv_path)
    monkeypatch.setattr(svc, "run_evaluation", lambda *a, **kw: {"total": 1, "evaluated_count": 1})
    res = client.post("/api/v1/evaluation/core", json={"limit": 2})
    assert res.status_code == 202
    job = svc.get_job_queue().get_job(res.json()["job_id"])
    assert job.status.value == "completed"
    assert job.result["total"] == 1 and job.result["limit"] == 2
