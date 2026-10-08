"""FEEDBACK-3 G15 — Sentry: disabled means disabled; 5xx, timeouts and
unhandled exceptions are captured with trace_id and without credentials; 4xx
is never captured; scheduler jobs and whole scrape runs that fail are captured
under their own trace_id.

``sentry_capture`` turns Sentry on against a fake DSN with an in-process
transport, so every event the SDK would send is observable and nothing leaves
the process. No test triggers the app lifespan (DB pool, scheduler).
"""
import json
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.config import settings
from src.core import sentry as sentry_module

FAKE_DSN = "https://publickey1234@o0.ingest.invalid/1"
SECRET_TOKEN = "s3cr3t-gateway-token-value-0123456789"
DB_PASSWORD = "dbPassw0rdXYZ"
TRACE_ID = "trace-abc123"
_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def secret_settings(monkeypatch):
    monkeypatch.setattr(settings, "API_TOKEN", SECRET_TOKEN)
    monkeypatch.setattr(settings, "DATABASE_URL", f"postgresql://scraper:{DB_PASSWORD}@db.internal:5432/pepti")
    yield


@pytest.fixture
def sentry_capture(monkeypatch, secret_settings):
    import sentry_sdk
    from sentry_sdk.transport import Transport

    class CaptureTransport(Transport):
        def __init__(self, options=None):
            super().__init__(options)
            self.events = []

        def capture_envelope(self, envelope):
            event = envelope.get_event()
            if event is not None:
                self.events.append(event)

        def flush(self, timeout, callback=None):
            return None

        def kill(self):
            return None

    transport = CaptureTransport()
    monkeypatch.setattr(settings, "SENTRY_DSN", FAKE_DSN)
    monkeypatch.setattr(sentry_module, "_initialized", False)
    assert sentry_module.init_sentry(transport=transport) is True
    try:
        yield transport.events
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()  # no DSN: an inactive client, integrations become no-ops
        sentry_module._initialized = False


@pytest.fixture
def app_client():
    """The real app and middleware stack, without running startup jobs."""
    from main import app

    added = []

    def add_route(path, endpoint, methods=("GET",)):
        app.add_api_route(path, endpoint, methods=list(methods))
        added.append(path)

    client = TestClient(app, raise_server_exceptions=False)
    client.add_route = add_route
    try:
        yield client
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) not in added]


def _auth_headers():
    return {
        "Authorization": f"Bearer {SECRET_TOKEN}",
        "X-Gateway-Token": SECRET_TOKEN,
        "X-Trace-Id": TRACE_ID,
    }


def _assert_clean(event):
    blob = json.dumps(event, default=str)
    for secret in (SECRET_TOKEN, DB_PASSWORD):
        assert secret not in blob, f"{secret[:6]}... leaked into the Sentry event"


# ---------------------------------------------------------------------------
# Disabled means disabled
# ---------------------------------------------------------------------------


class TestDisabledMeansDisabled:
    def test_empty_dsn_never_calls_sentry_sdk_init(self, monkeypatch):
        monkeypatch.setattr(settings, "SENTRY_DSN", "")
        monkeypatch.setattr(sentry_module, "_initialized", False)
        with patch("sentry_sdk.init") as init:
            assert sentry_module.init_sentry() is False
        init.assert_not_called()
        assert sentry_module.is_enabled() is False

    def test_capture_helpers_are_noops_when_disabled(self, monkeypatch):
        monkeypatch.setattr(sentry_module, "_initialized", False)
        with patch("sentry_sdk.capture_exception") as cap:
            sentry_module.capture_exception(RuntimeError("x"), status_code=500)
            sentry_module.capture_background_failure(RuntimeError("x"), job="j")
            sentry_module.capture_job_error(type("E", (), {"exception": RuntimeError("x"), "job_id": "j"})())
        cap.assert_not_called()

    def test_app_import_does_not_init_sentry_without_a_dsn(self, tmp_path):
        """Importing main (which calls init_sentry) in a clean interpreter with
        SENTRY_DSN empty never calls sentry_sdk.init."""
        env = {**os.environ, "SENTRY_DSN": "", "PYTHONPATH": str(_REPO_ROOT), "LOG_DIR": str(tmp_path)}
        code = (
            "from unittest.mock import patch\n"
            "import sentry_sdk\n"
            "with patch('sentry_sdk.init') as init:\n"
            "    import main\n"
            "assert not init.called, 'sentry_sdk.init was called'\n"
            "assert not sentry_sdk.get_client().is_active()\n"
            "print('ok')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=_REPO_ROOT, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr[-2000:]
        assert "ok" in result.stdout


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


class TestHttpCapture:
    def test_forced_500_event_has_trace_id_and_no_authorization_value(self, sentry_capture, app_client):
        def boom():
            # The message carries credentials on purpose: it must be scrubbed.
            raise RuntimeError(f"upstream rejected Bearer {SECRET_TOKEN} using {settings.DATABASE_URL}")

        app_client.add_route("/__test__/boom", boom)
        resp = app_client.get("/__test__/boom", headers=_auth_headers())

        assert resp.status_code == 500
        assert resp.json()["trace_id"] == TRACE_ID
        assert resp.headers["x-trace-id"] == TRACE_ID
        assert len(sentry_capture) == 1
        event = sentry_capture[0]
        assert event["tags"]["trace_id"] == TRACE_ID
        assert event["tags"]["service"] == "web_scrape"
        assert event["tags"].get("request_id") not in (None, "-")
        _assert_clean(event)
        headers = (event.get("request") or {}).get("headers") or {}
        for name, value in headers.items():
            if name.lower() in ("authorization", "x-gateway-token"):
                assert SECRET_TOKEN not in str(value)

    def test_http_exception_500_is_captured_with_the_original_error(self, sentry_capture, app_client):
        def wrapped():
            try:
                raise ValueError("database exploded")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        app_client.add_route("/__test__/wrapped500", wrapped)
        resp = app_client.get("/__test__/wrapped500", headers=_auth_headers())

        assert resp.status_code == 500
        assert resp.json() == {"detail": "database exploded"}  # response shape unchanged
        assert resp.headers["x-trace-id"] == TRACE_ID
        assert len(sentry_capture) == 1
        event = sentry_capture[0]
        assert event["exception"]["values"][-1]["type"] == "ValueError"
        assert event["tags"]["status_code"] == "500"
        assert event["tags"]["trace_id"] == TRACE_ID
        _assert_clean(event)

    def test_timeout_is_captured_and_tagged(self, sentry_capture, app_client):
        def slow():
            raise TimeoutError("competitor page timed out")

        app_client.add_route("/__test__/timeout", slow)
        resp = app_client.get("/__test__/timeout", headers={"X-Trace-Id": TRACE_ID})

        assert resp.status_code == 500
        assert len(sentry_capture) == 1
        assert sentry_capture[0]["tags"]["timeout"] == "true"

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
    def test_ordinary_4xx_is_not_captured(self, sentry_capture, app_client, status):
        def client_error():
            raise HTTPException(status_code=status, detail="nope")

        path = f"/__test__/c{status}"
        app_client.add_route(path, client_error)
        assert app_client.get(path, headers=_auth_headers()).status_code == status
        assert sentry_capture == []

    def test_unknown_route_404_is_not_captured(self, sentry_capture, app_client):
        assert app_client.get("/api/v1/no-such-route", headers=_auth_headers()).status_code == 404
        assert sentry_capture == []

    def test_missing_trace_header_gets_a_minted_one(self, sentry_capture, app_client):
        resp = app_client.get("/health")
        assert resp.status_code == 200
        assert len(resp.headers["x-trace-id"]) == 32

    def test_error_log_lines_do_not_become_events(self, sentry_capture):
        # A single competitor page that fails to parse is logged with
        # logger.exception inside the run — never an event on its own.
        try:
            raise ValueError("selector matched nothing")
        except ValueError:
            logging.getLogger("src.services.vendor_scraper").exception("Extraction failed for https://x")
        logging.getLogger("scheduler").error("handled failure, logged only")
        assert sentry_capture == []


# ---------------------------------------------------------------------------
# Background work
# ---------------------------------------------------------------------------


class TestBackgroundCapture:
    def test_failing_scheduler_job_produces_one_tagged_event(self, sentry_capture):
        from apscheduler.events import EVENT_JOB_ERROR
        from apscheduler.schedulers.background import BackgroundScheduler

        done = threading.Event()

        def failing_job():
            raise RuntimeError(f"job failed connecting to {settings.DATABASE_URL}")

        sched = BackgroundScheduler()
        sched.add_listener(sentry_module.capture_job_error, EVENT_JOB_ERROR)
        sched.add_listener(lambda _e: done.set(), EVENT_JOB_ERROR)
        sched.add_job(failing_job, id="failing_job", next_run_time=datetime.now(timezone.utc))
        sched.start()
        try:
            assert done.wait(10), "the job never ran"
        finally:
            sched.shutdown(wait=True)

        assert len(sentry_capture) == 1
        event = sentry_capture[0]
        assert event["tags"]["service"] == "web_scrape"
        assert event["tags"]["job"] == "failing_job"
        assert event["tags"]["source"] == "scheduler"
        assert event["tags"]["trace_id"] not in (None, "-")
        _assert_clean(event)

    def test_service_scheduler_has_the_listener(self):
        from apscheduler.events import EVENT_JOB_ERROR
        from src.core.scheduler import scheduler

        assert any(
            cb is sentry_module.capture_job_error and mask & EVENT_JOB_ERROR for cb, mask in scheduler._listeners
        )

    def test_vendor_scrape_run_failing_as_a_whole_is_one_event_with_its_own_trace(self, sentry_capture):
        from src.core import scheduler as sched_module

        with patch(
            "src.services.vendor_scrape_runner.run_vendor_scrape", side_effect=RuntimeError("targets table gone")
        ):
            assert sched_module.run_vendor_scrape_job() is None

        assert len(sentry_capture) == 1
        tags = sentry_capture[0]["tags"]
        assert tags["service"] == "web_scrape"
        assert tags["job"] == sched_module.VENDOR_SCRAPE_JOB_ID
        assert tags["trace_id"] not in (None, "-")

    def test_api_triggered_scrape_failure_mints_a_new_trace(self, sentry_capture):
        from src.api.v1.endpoints import vendors
        from src.core.job_queue import get_job_queue
        from src.core.request_context import bound_trace

        job = get_job_queue().create_job(vendors.SCRAPE_JOB_ENDPOINT, {})
        with patch.object(vendors, "run_vendor_scrape", side_effect=RuntimeError("browser crashed")):
            with bound_trace(TRACE_ID):
                vendors._run_scrape_task(job.job_id, None, None)

        assert len(sentry_capture) == 1
        tags = sentry_capture[0]["tags"]
        assert tags["trace_id"] not in (None, "-", TRACE_ID)
        assert tags["parent_trace_id"] == TRACE_ID
        assert tags["job_id"] == job.job_id


# ---------------------------------------------------------------------------
# Scrubber
# ---------------------------------------------------------------------------


class TestScrubber:
    def test_scrubber_failure_drops_the_event(self):
        with patch.object(sentry_module, "scrub_event", side_effect=RuntimeError("scrubber bug")):
            assert sentry_module._before_send({"message": "x"}, {}) is None

    def test_named_keys_header_pairs_and_values_are_masked(self, secret_settings, monkeypatch):
        monkeypatch.setenv("SOME_VENDOR_SECRET", "vendor-secret-value-42")
        event = {
            "request": {
                "headers": {"Authorization": f"Bearer {SECRET_TOKEN}", "X-Gateway-Token": SECRET_TOKEN},
                "data": {"q": "body"},
                "url": f"http://svc/x?token={SECRET_TOKEN}",
            },
            "extra": {
                "scope": {"headers": [(b"x-gateway-token", SECRET_TOKEN.encode()), (b"accept", b"*/*")]},
                "API_TOKEN": SECRET_TOKEN,
                "db_password": "anything",
                "DATABASE_URL": settings.DATABASE_URL,
                "note": f"dsn postgresql://u:{DB_PASSWORD}@h/db and env vendor-secret-value-42",
            },
        }
        out = sentry_module.scrub_event(event)
        blob = json.dumps(out, default=str)
        for secret in (SECRET_TOKEN, DB_PASSWORD, "vendor-secret-value-42", "anything"):
            assert secret not in blob
        assert "data" not in out["request"]
        assert out["request"]["url"] == "http://svc/x"
        assert out["extra"]["scope"]["headers"][1][0] == "accept"  # bytes are decoded, not masked
        assert out["tags"]["service"] == "web_scrape"

    def test_init_options_follow_the_shared_rules(self, monkeypatch):
        monkeypatch.setattr(settings, "SENTRY_DSN", "https://k@o0.ingest.invalid/1")
        monkeypatch.setattr(settings, "SENTRY_RELEASE", "")
        monkeypatch.setenv("GIT_SHA", "abc1234")
        monkeypatch.setattr(sentry_module, "_initialized", False)
        with patch("sentry_sdk.init") as init, patch("sentry_sdk.set_tag"):
            assert sentry_module.init_sentry() is True
        monkeypatch.setattr(sentry_module, "_initialized", False)
        kwargs = init.call_args.kwargs
        assert kwargs["include_local_variables"] is False
        assert kwargs["send_default_pii"] is False
        assert kwargs["before_send"] is sentry_module._before_send
        assert kwargs["event_scrubber"].recursive is True
        assert kwargs["release"] == "abc1234"
        assert kwargs["traces_sample_rate"] == 0.0
