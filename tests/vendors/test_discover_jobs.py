"""Async discover preview (AID-2): start returns a job id at once, the client polls.

The synchronous ``POST /vendors/discover`` paces itself (>= 5 s per store
request) and routinely outlasts the gateway's timeout, so the admin starts a job
instead. The old route stays, unchanged, for clients that still call it.
Everything here is offline: the preview itself is a fake.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import vendors
from app.controllers.vendor_discover_controller import MAX_RUNNING_PREVIEWS, VendorDiscoverController
from app.core.errors import ConflictError
from app.core.job_queue import JobStatus, get_job_queue
from app.services import vendor_target_service

URL = "https://rival.example/"
PREVIEW = {"url": URL, "method": "woocommerce", "requests_made": 7, "readings": [{"name": "BPC-157", "price": "40"}]}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(vendor_target_service, "check_url", lambda url: None)
    queue = get_job_queue()
    queue.jobs.clear()
    app = FastAPI()
    app.include_router(vendors.router, prefix="/api/v1/vendors")
    yield TestClient(app)
    queue.jobs.clear()


def _fake_preview(monkeypatch, fn):
    monkeypatch.setattr(vendor_target_service, "preview_discovery", fn)


def test_start_returns_a_job_id_before_the_preview_runs(client, monkeypatch):
    _fake_preview(monkeypatch, lambda url, max_products, currency: PREVIEW)
    scheduled = []
    body = VendorDiscoverController(lambda fn, *a: scheduled.append((fn, a))).start(URL, 5, None)
    assert body["job_id"]
    assert body["status"] == "pending"
    assert len(scheduled) == 1  # nothing ran yet: the caller already has its id
    assert get_job_queue().get_job(body["job_id"]).status is JobStatus.PENDING
    fn, args = scheduled[0]
    fn(*args)
    assert get_job_queue().get_job(body["job_id"]).status is JobStatus.COMPLETED


def test_poll_returns_the_preview_when_done(client, monkeypatch):
    _fake_preview(monkeypatch, lambda url, max_products, currency: PREVIEW)
    started = client.post("/api/v1/vendors/discover/jobs", json={"url": URL, "max_products": 3})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    polled = client.get(f"/api/v1/vendors/discover/jobs/{job_id}")
    assert polled.status_code == 200
    body = polled.json()
    assert body["status"] == "completed"
    assert body["progress"] == 100
    assert body["result"] == PREVIEW
    assert body["error"] is None


def test_preview_arguments_reach_the_preview(client, monkeypatch):
    seen = {}

    def preview(url, max_products, currency):
        seen.update(url=url, max_products=max_products, currency=currency)
        return PREVIEW

    _fake_preview(monkeypatch, preview)
    client.post("/api/v1/vendors/discover/jobs", json={"url": f" {URL} ", "max_products": 4, "currency": "USD"})
    assert seen == {"url": URL, "max_products": 4, "currency": "USD"}


def test_a_failed_preview_is_a_failed_job_with_the_reason(client, monkeypatch):
    def boom(url, max_products, currency):
        raise RuntimeError("store refused us")

    _fake_preview(monkeypatch, boom)
    job_id = client.post("/api/v1/vendors/discover/jobs", json={"url": URL}).json()["job_id"]
    body = client.get(f"/api/v1/vendors/discover/jobs/{job_id}").json()
    assert body["status"] == "failed"
    assert "store refused us" in body["error"]
    assert body["result"] is None


def test_a_bad_url_is_refused_at_start_like_the_sync_route(client):
    res = client.post("/api/v1/vendors/discover/jobs", json={"url": "ftp://rival.example/x"})
    assert res.status_code == 422
    assert get_job_queue().list_jobs() == []


def test_unknown_job_is_404_and_a_scrape_job_is_not_a_discover_job(client):
    assert client.get("/api/v1/vendors/discover/jobs/nope").status_code == 404
    scrape = get_job_queue().create_job("/vendors/scrape", {})
    assert client.get(f"/api/v1/vendors/discover/jobs/{scrape.job_id}").status_code == 404


def test_same_url_while_running_returns_the_running_job(client):
    ctrl = VendorDiscoverController(lambda fn, *a: None)  # never runs: the job stays pending
    first = ctrl.start(URL, 5, None)
    second = ctrl.start(URL, 5, None)
    assert second["job_id"] == first["job_id"]
    assert len(get_job_queue().list_jobs()) == 1


def test_too_many_previews_at_once_is_409(client):
    ctrl = VendorDiscoverController(lambda fn, *a: None)
    for n in range(MAX_RUNNING_PREVIEWS):
        ctrl.start(f"https://rival{n}.example/", 5, None)
    with pytest.raises(ConflictError):
        ctrl.start("https://one-more.example/", 5, None)


def test_the_synchronous_route_is_unchanged(client, monkeypatch):
    _fake_preview(monkeypatch, lambda url, max_products, currency: PREVIEW)
    res = client.post("/api/v1/vendors/discover", json={"url": URL})
    assert res.status_code == 200
    assert res.json() == PREVIEW
