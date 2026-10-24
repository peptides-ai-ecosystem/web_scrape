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
    _fake_preview(monkeypatch, lambda url, max_products, currency, should_stop=None: PREVIEW)
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
    _fake_preview(monkeypatch, lambda url, max_products, currency, should_stop=None: PREVIEW)
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

    def preview(url, max_products, currency, should_stop=None):
        seen.update(url=url, max_products=max_products, currency=currency)
        return PREVIEW

    _fake_preview(monkeypatch, preview)
    client.post("/api/v1/vendors/discover/jobs", json={"url": f" {URL} ", "max_products": 4, "currency": "USD"})
    assert seen == {"url": URL, "max_products": 4, "currency": "USD"}


def test_a_failed_preview_is_a_failed_job_with_the_reason(client, monkeypatch):
    def boom(url, max_products, currency, should_stop=None):
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
    _fake_preview(monkeypatch, lambda url, max_products, currency, should_stop=None: PREVIEW)
    res = client.post("/api/v1/vendors/discover", json={"url": URL})
    assert res.status_code == 200
    assert res.json() == PREVIEW


# ---------------------------------------------------------------------------
# Review notes: deadline, cancel, dedupe key, cleanup, crawl-delay cap
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    from app.controllers import vendor_discover_controller as ctrl

    fake = FakeClock()
    monkeypatch.setattr(ctrl, "_clock", fake)
    return fake


def _run_started(body):
    """Run what the controller scheduled (the job id comes from ``body``)."""
    return get_job_queue().get_job(body["job_id"])


def test_deadline_stops_a_slow_preview_with_partial_results(client, monkeypatch, clock):
    from app.core.config import settings

    monkeypatch.setattr(settings, "VENDOR_DISCOVERY_DEADLINE_SECONDS", 300)
    stops = []

    def slow(url, max_products, currency, should_stop=None):
        stops.append(should_stop())  # inside the deadline
        clock.now += 301  # the store is slow
        stops.append(should_stop())  # past it: the discovery loop must wind down
        return {"url": url, "readings": [{"name": "partial"}], "requests_made": 3}

    _fake_preview(monkeypatch, slow)
    job_id = client.post("/api/v1/vendors/discover/jobs", json={"url": URL}).json()["job_id"]
    assert stops == [False, True]
    body = client.get(f"/api/v1/vendors/discover/jobs/{job_id}").json()
    assert body["status"] == "completed"
    assert body["result"]["stopped_early"] is True
    assert body["result"]["readings"] == [{"name": "partial"}]


def test_a_preview_inside_its_deadline_is_not_marked_early(client, monkeypatch, clock):
    _fake_preview(monkeypatch, lambda url, max_products, currency, should_stop=None: dict(PREVIEW))
    job_id = client.post("/api/v1/vendors/discover/jobs", json={"url": URL}).json()["job_id"]
    assert "stopped_early" not in client.get(f"/api/v1/vendors/discover/jobs/{job_id}").json()["result"]


def test_a_cancelled_job_is_never_overwritten_and_the_thread_is_told_to_stop(client, monkeypatch, clock):
    seen = {}

    def preview(url, max_products, currency, should_stop=None):
        job = get_job_queue().list_jobs()[0]
        job.cancel()
        seen["stop"] = should_stop()
        return dict(PREVIEW)

    _fake_preview(monkeypatch, preview)
    job_id = client.post("/api/v1/vendors/discover/jobs", json={"url": URL}).json()["job_id"]
    assert seen["stop"] is True
    body = client.get(f"/api/v1/vendors/discover/jobs/{job_id}").json()
    assert body["status"] == "cancelled"
    assert body["result"] is None


def test_a_cancelled_job_that_then_fails_stays_cancelled(client, monkeypatch, clock):
    def preview(url, max_products, currency, should_stop=None):
        get_job_queue().list_jobs()[0].cancel()
        raise RuntimeError("late failure")

    _fake_preview(monkeypatch, preview)
    job_id = client.post("/api/v1/vendors/discover/jobs", json={"url": URL}).json()["job_id"]
    body = client.get(f"/api/v1/vendors/discover/jobs/{job_id}").json()
    assert body["status"] == "cancelled"
    assert body["error"] is None


def test_same_url_with_other_options_is_its_own_job(client):
    ctrl = VendorDiscoverController(lambda fn, *a: None)
    first = ctrl.start(URL, 5, None)
    other_options = ctrl.start(URL, 10, "USD")
    same = ctrl.start(URL, 5, None)
    assert other_options["job_id"] != first["job_id"]
    assert same["job_id"] == first["job_id"]


def test_another_url_of_a_busy_host_waits_for_the_host_instead_of_doubling_the_rate(client, monkeypatch):
    """Two previews of one host never run at once (each builds its own limiter)."""
    import threading

    in_flight = {"now": 0, "max": 0}
    guard = threading.Lock()
    release = threading.Event()

    def preview(url, max_products, currency, should_stop=None):
        with guard:
            in_flight["now"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["now"])
        release.wait(2)
        with guard:
            in_flight["now"] -= 1
        return dict(PREVIEW)

    _fake_preview(monkeypatch, preview)
    scheduled = []
    ctrl = VendorDiscoverController(lambda fn, *a: scheduled.append((fn, a)))
    ctrl.start("https://rival.example/", 5, None)
    ctrl.start("https://rival.example/shop", 5, None)
    threads = [threading.Thread(target=fn, args=a) for fn, a in scheduled]
    for t in threads:
        t.start()
    release.set()
    for t in threads:
        t.join(5)
    assert in_flight["max"] == 1
    assert {j.status for j in get_job_queue().list_jobs()} == {JobStatus.COMPLETED}


def test_starting_a_job_drops_old_finished_ones(client):
    queue = get_job_queue()
    old = queue.create_job("/vendors/discover", {"url": "https://old.example/"})
    old.complete({})
    from datetime import timedelta

    old.end_time = old.end_time - timedelta(hours=25)
    VendorDiscoverController(lambda fn, *a: None).start(URL, 5, None)
    assert queue.get_job(old.job_id) is None


def test_crawl_delay_is_capped_for_a_preview_but_not_without_a_cap():
    from app.infrastructure.polite_http import PoliteHttpClient
    from app.infrastructure.rate_limiter import HostRateLimiter

    class Robots:
        user_agent = "t"

        def is_allowed(self, url):
            return True

        def crawl_delay(self, url):
            return 600.0

    def acquire(cap):
        slept = []
        limiter = HostRateLimiter(default_interval=0.0, base_backoff=0.0, clock=lambda: 0.0, sleeper=slept.append)
        client = PoliteHttpClient(Robots(), limiter, max_crawl_delay=cap)
        import app.infrastructure.polite_http as ph

        orig = ph.check_url
        ph.check_url = lambda url: None
        try:
            client.acquire("https://rival.example/a")
        finally:
            ph.check_url = orig
        return limiter.interval_for("rival.example")

    assert acquire(15.0) == 15.0
    assert acquire(None) == 600.0


def test_the_client_stops_asking_once_told_to_stop():
    from app.infrastructure.polite_http import PoliteHttpClient
    from app.infrastructure.rate_limiter import HostRateLimiter

    class Robots:
        user_agent = "t"

        def is_allowed(self, url):
            raise AssertionError("a stopped client must not even read robots")

    client = PoliteHttpClient(Robots(), HostRateLimiter(default_interval=0.0), should_stop=lambda: True)
    result = client.acquire("https://rival.example/a")
    assert result is not None
    assert result.budget_exhausted
    assert client.requests_made == 0
