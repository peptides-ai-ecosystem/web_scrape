"""``/api/v1/operations`` routes call ``job_service``; status codes and bodies are unchanged."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import operations
from app.core.job_queue import get_job_queue


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(operations.router, prefix="/api/v1/operations")
    return TestClient(app)


def test_invalid_status_filter_is_400(client):
    res = client.get("/api/v1/operations/jobs", params={"status": "nope"})
    assert res.status_code == 400
    assert res.json()["detail"].startswith("Invalid status 'nope'. Must be one of: pending")


def test_job_lifecycle(client):
    job = get_job_queue().create_job("/ops-test", {})
    assert client.get(f"/api/v1/operations/job/{job.job_id}").json()["status"] == "pending"
    cancelled = client.delete(f"/api/v1/operations/job/{job.job_id}").json()
    assert cancelled["message"] == f"Job {job.job_id} cancelled"
    again = client.delete(f"/api/v1/operations/job/{job.job_id}")
    assert again.status_code == 400
    assert again.json()["detail"].startswith("Cannot cancel job in 'cancelled' status.")


def test_unknown_job_is_404(client):
    res = client.get("/api/v1/operations/job/missing")
    assert res.status_code == 404 and res.json()["detail"] == "Job missing not found"
    assert client.delete("/api/v1/operations/job/missing").status_code == 404


def test_health_counts(client):
    body = client.get("/api/v1/operations/health").json()
    assert body["status"] == "healthy"
    assert set(body["stats"]) == {"pending", "running", "completed", "failed", "cancelled"}
