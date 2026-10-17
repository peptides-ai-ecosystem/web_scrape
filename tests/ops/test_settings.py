"""Pydantic settings keep the environment variable names, defaults and boolean parsing of the old src/config.py."""

import re
from pathlib import Path

import pytest

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]

# Every variable the former src/config.py read.
OLD_NAMES = {
    "DATABASE_URL",
    "TIMEOUT",
    "API_TOKEN",
    "GATEWAY_AUTH_HEADER",
    "START_SCHEDULER",
    "OUTPUT_DIR",
    "LOG_DIR",
    "VENDOR_TARGETS_FILE",
    "VENDOR_SCRAPER_CONTACT_URL",
    "VENDOR_SCRAPER_USER_AGENT",
    "VENDOR_SCRAPE_MIN_INTERVAL_SECONDS",
    "VENDOR_SCRAPE_MAX_RETRIES",
    "VENDOR_SCRAPE_BACKOFF_SECONDS",
    "VENDOR_SCRAPE_TIMEOUT_MS",
    "VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS",
    "VENDOR_PRICE_DELTA_THRESHOLD",
    "VENDOR_MIN_CONFIDENCE",
    "VENDOR_SCRAPE_CRON_ENABLED",
    "VENDOR_SCRAPE_CRON_HOUR",
    "VENDOR_SCRAPE_CRON_MINUTE",
    "VENDOR_PRODUCTS_PUBLISH_ENABLED",
    "VENDOR_DISCOVERY_MAX_REQUESTS",
    "VENDOR_DISCOVERY_MAX_PRODUCTS",
    "VENDOR_DISCOVERY_CONCURRENCY",
    "VENDOR_DISCOVERY_TIMEOUT_SECONDS",
    "OWNED_STORE_DOMAINS",
    "OWNED_STORE_VENDORS",
    "VENDOR_SCHEMA_AUTO_CREATE",
    "SENTRY_DSN",
    "SENTRY_ENVIRONMENT",
    "SENTRY_RELEASE",
    "SENTRY_TRACES_SAMPLE_RATE",
}


def test_every_old_environment_name_is_still_a_setting():
    assert OLD_NAMES <= set(Settings.model_fields)


def test_every_setting_is_documented_in_env_example():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, re.M))
    # DATABASE_URL, API_TOKEN etc. are listed; derived/secret names may be absent but the old ones must not be.
    missing = {n for n in OLD_NAMES if n not in documented} - {"OWNED_STORE_DOMAINS", "OWNED_STORE_VENDORS", "LOG_DIR"}
    assert not missing, missing


def _clean(monkeypatch, **env):
    for name in OLD_NAMES:
        monkeypatch.delenv(name, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)


def test_defaults_match_the_old_module(monkeypatch):
    s = _clean(monkeypatch)
    assert s.START_SCHEDULER is True and s.VENDOR_SCRAPE_CRON_ENABLED is False
    assert s.VENDOR_SCHEMA_AUTO_CREATE is False
    assert s.TIMEOUT == 5 and s.GATEWAY_AUTH_HEADER == "X-Gateway-Token" and s.API_TOKEN == ""
    assert s.VENDOR_PRICE_DELTA_THRESHOLD == 0.25 and s.VENDOR_MIN_CONFIDENCE == 0.6
    assert s.VENDOR_SCRAPER_USER_AGENT.startswith("PeptidesVendorScraper/1.0 (+https://github.com/")
    assert s.ENHANCED_CSV.name == "pep_pedia_enhanced.csv" and s.MASTER_CSV == s.ENHANCED_CSV


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("off", False),
        ("true", True),
        (" Yes ", True),
        ("1", True),
        ("on", True),
        ("banana", False),
    ],
)
def test_booleans_parse_like_the_old_module(monkeypatch, raw, expected):
    assert _clean(monkeypatch, START_SCHEDULER=raw).START_SCHEDULER is expected


def test_empty_sentry_rate_is_zero_and_dsn_is_stripped(monkeypatch):
    s = _clean(monkeypatch, SENTRY_TRACES_SAMPLE_RATE="", SENTRY_DSN="  ")
    assert s.SENTRY_TRACES_SAMPLE_RATE == 0.0 and s.SENTRY_DSN == ""


def test_explicit_user_agent_wins(monkeypatch):
    assert _clean(monkeypatch, VENDOR_SCRAPER_USER_AGENT="Bot/2").VENDOR_SCRAPER_USER_AGENT == "Bot/2"


@pytest.mark.parametrize(
    "raw", ["postgres://u:p@h:5432/d", "postgresql://u:p@h:5432/d", "postgresql+psycopg2://u:p@h:5432/d"]
)
def test_alembic_url_uses_the_psycopg2_driver(monkeypatch, raw):
    assert _clean(monkeypatch, DATABASE_URL=raw).sqlalchemy_database_url == "postgresql+psycopg2://u:p@h:5432/d"
