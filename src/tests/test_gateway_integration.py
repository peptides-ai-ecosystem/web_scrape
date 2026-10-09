"""Gateway-integration tests for the web_scrape API server.

These tests deliberately avoid triggering the FastAPI lifespan (which warms a
PostgreSQL pool and starts APScheduler), so they exercise the auth dependency
directly and inspect route registration on the app object.
"""
import pytest

from src.api.gateway_auth import require_gateway_token
from fastapi import HTTPException


@pytest.fixture
def no_gateway_token(monkeypatch):
    """Simulate API_TOKEN unset — auth is skipped (local dev)."""
    import src.api.gateway_auth as ga

    monkeypatch.setattr(ga, "API_TOKEN", "")
    return ga


@pytest.fixture
def with_gateway_token(monkeypatch):
    """Simulate API_TOKEN set to a known value."""
    import src.api.gateway_auth as ga

    monkeypatch.setattr(ga, "API_TOKEN", "test-gateway-token")
    return ga


def test_health_route_registered():
    import web_scrape.main as main

    paths = {route.path for route in main.app.routes}
    assert "/health" in paths


def test_health_reports_the_commit_the_image_was_built_from(monkeypatch):
    """FEEDBACK-3 G36: the EC2 host holds no source, so /health says which
    commit is running (the deploy's GIT_SHA build arg)."""
    import asyncio

    import main

    monkeypatch.setenv("GIT_SHA", "ac49ca9")
    assert asyncio.run(main.health())["commit"] == "ac49ca9"
    monkeypatch.delenv("GIT_SHA")
    assert asyncio.run(main.health())["commit"] == "unknown"


def test_api_router_has_auth_dependency():
    from src.api.v1.routers import api_router

    assert api_router.dependencies, "api_router must enforce gateway auth"


def test_auth_skipped_when_token_unset(no_gateway_token):
    # Local dev without API_TOKEN: the dependency is a no-op.
    assert require_gateway_token(x_gateway_token=None) is None
    assert require_gateway_token(x_gateway_token="anything") is None


def test_auth_rejects_missing_token(with_gateway_token):
    with pytest.raises(HTTPException) as exc:
        require_gateway_token(x_gateway_token=None)
    assert exc.value.status_code == 401


def test_auth_rejects_wrong_token(with_gateway_token):
    with pytest.raises(HTTPException) as exc:
        require_gateway_token(x_gateway_token="wrong")
    assert exc.value.status_code == 401


def test_auth_accepts_matching_token(with_gateway_token):
    assert require_gateway_token(x_gateway_token="test-gateway-token") is None
