"""MS:webscrape-3: an empty API_TOKEN must not leave the API open.

Same posture as admin and peptide: 503 "authentication is not configured",
with one explicit local-only opt-out (ALLOW_UNAUTHENTICATED=true and
ENVIRONMENT in local/dev/development).
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.api.gateway_auth as ga
from app.api.gateway_auth import require_gateway_token
from app.core.config import settings


@pytest.fixture
def empty_token(monkeypatch):
    monkeypatch.setattr(ga, "API_TOKEN", "")
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "")


def test_empty_token_without_the_flag_is_503(empty_token):
    for presented in (None, "anything"):
        with pytest.raises(HTTPException) as exc:
            require_gateway_token(x_gateway_token=presented)
        assert exc.value.status_code == 503
        assert "not configured" in exc.value.detail


def test_flag_alone_is_not_enough_outside_local(empty_token, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", True)
    for env in ("", "staging", "production"):
        monkeypatch.setattr(settings, "ENVIRONMENT", env)
        with pytest.raises(HTTPException) as exc:
            require_gateway_token(x_gateway_token=None)
        assert exc.value.status_code == 503


@pytest.mark.parametrize("env", ["local", "dev", "development", " Local "])
def test_flag_in_local_environment_opens_the_api(empty_token, monkeypatch, env):
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", env)
    assert require_gateway_token(x_gateway_token=None) is None


def test_local_environment_without_the_flag_is_503(empty_token, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "local")
    with pytest.raises(HTTPException) as exc:
        require_gateway_token(x_gateway_token=None)
    assert exc.value.status_code == 503


def test_set_token_behaves_as_before_whatever_the_flag(monkeypatch):
    monkeypatch.setattr(ga, "API_TOKEN", "secret")
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "local")
    assert require_gateway_token(x_gateway_token="secret") is None
    for bad in (None, "wrong"):
        with pytest.raises(HTTPException) as exc:
            require_gateway_token(x_gateway_token=bad)
        assert exc.value.status_code == 401


def test_health_stays_open_and_the_api_is_503_over_http(empty_token):
    import main

    client = TestClient(main.app, raise_server_exceptions=False)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/vendors/targets").status_code == 503
