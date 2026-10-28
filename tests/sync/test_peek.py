"""AWD-17: the reference-page peek shows what a core sync would write and stores nothing.

Offline: the browser read is a fake, the allow-list and the mappers are real.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import sync
from app.controllers import peek_controller
from app.controllers.peek_controller import PeekController
from app.core.config import settings
from app.core.errors import ConflictError, InvalidInputError
from app.core.job_queue import JobStatus, get_job_queue
from app.core.models import HeroData, HeroFact, PeptideData
from app.infrastructure import reference_url, url_safety
from app.infrastructure.reference_url import check_reference_url, final_url_allowed
from app.infrastructure.url_safety import UnsafeTargetURLError
from app.services import peek_service
from app.services.peek_service import build_peek

URL = "https://pep-pedia.org/peptides/bpc-157"


def _page(method="Injectable", url=URL, level="Well Researched") -> PeptideData:
    return PeptideData(
        name="BPC-157",
        full_name="Body Protection Compound-157",
        method=method,
        url=url,
        hero=HeroData(
            name="BPC-157",
            subtitle="Body Protection Compound-157",
            facts=[HeroFact("Cycle", "4-6 weeks", "")],
            research_level=level,
        ),
        quick_guide={"Onset": "1-2 weeks", "Half life": "4 hours"},
        sections=[
            {"overview_what_is_bpc_157": "A gastric pentadecapeptide."},
            {"overview_key_benefits": "Supports tendon repair. Reduces gut inflammation."},
            {"side_effects_and_safety_side_effects_1": "Mild nausea. Dizziness."},
        ],
    )


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """No real DNS: every host resolves to a public address."""
    monkeypatch.setattr(url_safety, "_system_resolver", lambda host: ["93.184.216.34"])
    get_job_queue().jobs.clear()
    yield
    get_job_queue().jobs.clear()


# ── the allow-list (SSRF) ───────────────────────────────────────────────────


def test_a_reference_page_url_is_accepted_and_the_fragment_dropped():
    assert check_reference_url(URL + "#overview") == URL
    assert (
        check_reference_url("https://www.pep-pedia.org/peptides/bpc-157")
        == "https://www.pep-pedia.org/peptides/bpc-157"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "http://pep-pedia.org/peptides/bpc-157",  # not https
        "https://evil.example/peptides/bpc-157",  # not on the list
        "https://pep-pedia.org.evil.example/peptides/x",  # suffix trick
        "https://evil.example/pep-pedia.org",  # path trick
        "https://sub.pep-pedia.org/peptides/x",  # sub-domains are not implied
        "https://user:pw@pep-pedia.org/peptides/x",  # credentials
        "https://pep-pedia.org:8443/peptides/x",  # other port
        "https://pep-pedia.org@evil.example/peptides/x",  # userinfo host trick
        "https://127.0.0.1/peptides/x",
        "https://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://pep-pedia.org/peptides/x y",  # whitespace
        "",
    ],
)
def test_urls_off_the_allow_list_are_refused(bad):
    with pytest.raises(UnsafeTargetURLError):
        check_reference_url(bad)


def test_an_allowed_name_that_resolves_to_a_private_address_is_refused(monkeypatch):
    monkeypatch.setattr(url_safety, "_system_resolver", lambda host: ["10.0.0.5"])
    with pytest.raises(UnsafeTargetURLError):
        check_reference_url(URL)


def test_the_allow_list_comes_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "PEEK_ALLOWED_HOSTS", "reference.example")
    assert reference_url.allowed_hosts() == frozenset({"reference.example"})
    assert check_reference_url("https://reference.example/p/1")
    with pytest.raises(UnsafeTargetURLError):
        check_reference_url(URL)


def test_a_redirect_off_the_list_is_detected():
    assert final_url_allowed(URL)
    assert not final_url_allowed("https://evil.example/")
    assert not final_url_allowed("http://pep-pedia.org/peptides/bpc-157")
    assert not final_url_allowed(None)


# ── the payload ─────────────────────────────────────────────────────────────


def test_build_peek_maps_the_page_like_the_core_sync():
    out = build_peek(URL, [_page()])
    assert out["name"] == "BPC-157" and out["slug"] == "bpc-157"
    assert out["peptide"]["overview"] == "A gastric pentadecapeptide."
    assert out["peptide"]["cycle_duration"]
    assert out["peptide"]["effect_onset"] == "1-2 weeks"
    assert out["peptide"]["half_life_value"] == 4.0 and out["peptide"]["half_life_unit"] == "hours"
    assert out["benefits"] == ["Supports tendon repair", "Reduces gut inflammation"]
    assert out["side_effects"] == ["Mild nausea", "Dizziness"]
    assert out["research_stage"] == "Well Researched"
    assert out["warnings"] == []
    assert out["methods"] == [{"label": "Injectable", "resolved": "Injectable", "reason": None}]


def test_the_research_stage_is_not_a_peptide_column():
    out = build_peek(URL, [_page()])
    assert "research_stage" not in out["peptide"] and "research_level" not in out["peptide"]


def test_several_methods_merge_first_value_wins_and_an_unmapped_method_warns():
    second = _page(method="Sublingual drops")
    second.quick_guide = {"Onset": "5 days"}
    out = build_peek(URL, [_page(), second])
    assert out["peptide"]["effect_onset"] == "1-2 weeks"  # the first method's value stays
    assert [m["resolved"] for m in out["methods"]] == ["Injectable", None]
    assert len(out["warnings"]) == 1 and "Sublingual drops" in out["warnings"][0]


def test_building_a_peek_touches_no_database(monkeypatch):
    import app.services.sync.db_import_orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module, "DbManager", lambda *a, **k: pytest.fail("peek must not open a database"))
    build_peek(URL, [_page()])


# ── the job ─────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(sync.router, prefix="/api/v1/sync")
    return TestClient(app)


def _scraper(monkeypatch, results, errors=None):
    monkeypatch.setattr(peek_service, "scrape_reference_page", lambda url, *a: (results, errors or []))


def test_start_returns_a_job_id_then_the_payload_when_polled(client, monkeypatch):
    _scraper(monkeypatch, [_page()])
    started = client.post("/api/v1/sync/peek", json={"url": URL})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    body = client.get(f"/api/v1/sync/peek/jobs/{job_id}").json()
    assert body["status"] == "completed" and body["progress"] == 100
    assert body["url"] == URL
    assert body["result"]["slug"] == "bpc-157"
    assert body["error"] is None


def test_a_url_off_the_list_is_a_422_and_starts_nothing(client, monkeypatch):
    _scraper(monkeypatch, [_page()])
    res = client.post("/api/v1/sync/peek", json={"url": "https://evil.example/peptides/x"})
    assert res.status_code == 422
    assert get_job_queue().jobs == {}


def test_a_redirect_off_the_list_fails_the_job_and_returns_nothing(client, monkeypatch):
    _scraper(monkeypatch, [_page(url="https://evil.example/landing")])
    job_id = client.post("/api/v1/sync/peek", json={"url": URL}).json()["job_id"]
    body = client.get(f"/api/v1/sync/peek/jobs/{job_id}").json()
    assert body["status"] == "failed" and "redirected" in body["error"]
    assert body["result"] is None


def test_a_page_with_nothing_on_it_fails_with_the_reason(client, monkeypatch):
    _scraper(monkeypatch, [], [{"url": URL, "category": None, "error": "404 not found"}])
    job_id = client.post("/api/v1/sync/peek", json={"url": URL}).json()["job_id"]
    body = client.get(f"/api/v1/sync/peek/jobs/{job_id}").json()
    assert body["status"] == "failed" and "404 not found" in body["error"]


def test_a_browser_crash_fails_the_job(client, monkeypatch):
    def boom(url, *a):
        raise RuntimeError("chrome crashed")

    monkeypatch.setattr(peek_service, "scrape_reference_page", boom)
    job_id = client.post("/api/v1/sync/peek", json={"url": URL}).json()["job_id"]
    body = client.get(f"/api/v1/sync/peek/jobs/{job_id}").json()
    assert body["status"] == "failed" and "chrome crashed" in body["error"]


def test_a_page_that_never_loads_is_given_up_after_the_timeout(client, monkeypatch):
    import threading

    gate = threading.Event()
    monkeypatch.setattr(peek_service, "scrape_reference_page", lambda url, *a: gate.wait(5) or ([], []))
    monkeypatch.setattr(settings, "PEEK_TIMEOUT_SECONDS", 0.05)
    job_id = client.post("/api/v1/sync/peek", json={"url": URL}).json()["job_id"]
    gate.set()
    body = client.get(f"/api/v1/sync/peek/jobs/{job_id}").json()
    assert body["status"] == "failed" and "not fully read" in body["error"]


def test_a_timed_out_peek_holds_its_slot_until_the_browser_thread_exits(monkeypatch):
    import threading

    gate = threading.Event()
    seen = {}

    def hang(url, timeout=None):
        seen["timeout"] = timeout
        gate.wait(5)
        return [], []

    monkeypatch.setattr(peek_service, "scrape_reference_page", hang)
    monkeypatch.setattr(settings, "PEEK_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(settings, "PEEK_MAX_RUNNING", 1)
    controller = PeekController(lambda fn, *a: fn(*a))
    job_id = controller.start(URL)["job_id"]
    assert controller.get_job(job_id)["status"] == "failed"
    assert seen["timeout"] == 0.05  # the driver page load is capped to the same value
    with pytest.raises(ConflictError):  # still counted: its Chrome has not exited
        controller.start("https://pep-pedia.org/peptides/tb-500")
    gate.set()
    peek_controller._live_threads[job_id].join(2)
    monkeypatch.setattr(peek_service, "scrape_reference_page", lambda url, *a: ([_page()], []))
    controller.start("https://pep-pedia.org/peptides/tb-500")


def test_the_same_url_while_running_returns_the_running_job(monkeypatch):
    scheduled = []
    controller = PeekController(lambda fn, *a: scheduled.append((fn, a)))
    first = controller.start(URL)
    again = controller.start(URL)
    assert first["job_id"] == again["job_id"] and len(scheduled) == 1


def test_too_many_browsers_at_once_is_a_409(monkeypatch):
    monkeypatch.setattr(settings, "PEEK_MAX_RUNNING", 1)
    controller = PeekController(lambda fn, *a: None)
    controller.start(URL)
    with pytest.raises(ConflictError):
        controller.start("https://pep-pedia.org/peptides/tb-500")


def test_start_refuses_an_off_list_url_with_a_422_error():
    with pytest.raises(InvalidInputError):
        PeekController(lambda fn, *a: None).start("http://pep-pedia.org/peptides/x")


def test_polling_an_unknown_or_foreign_job_is_a_404(client):
    assert client.get("/api/v1/sync/peek/jobs/nope").status_code == 404
    other = get_job_queue().create_job("/sync/graph", {})
    assert client.get(f"/api/v1/sync/peek/jobs/{other.job_id}").status_code == 404


def test_a_cancelled_job_is_never_overwritten(monkeypatch):
    queue = get_job_queue()
    job = queue.create_job(peek_controller.PEEK_JOB_ENDPOINT, {"url": URL})
    job.cancel()
    peek_controller._run_peek_task(job.job_id, URL)
    assert job.status is JobStatus.CANCELLED


def test_the_route_sits_behind_the_gateway_token():
    from app.api.v1.routers import api_router

    paths = {route.path for route in api_router.routes}
    assert "/sync/peek" in paths and "/sync/peek/jobs/{job_id}" in paths
    assert api_router.dependencies, "the router carries the gateway-token dependency"
