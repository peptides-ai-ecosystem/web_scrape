"""Tests for API-managed competitor targets, listing discovery, progress and the
admin-facing endpoints (CEO feedback round 2, P2).

Everything here is offline except :class:`TestLocalFixtureSite`, which serves
``src/tests/fixtures/competitor_site`` from a throwaway ``http.server`` on
127.0.0.1 and points the real Playwright fetcher at it. **No test ever reaches
a real competitor site.** That class skips itself when no Chromium can be
launched (set ``CHROME_BIN`` to an installed Chromium to run it).
"""
import asyncio
import functools
import http.server
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.core.vendor_models import (
    FieldSelectors,
    ReviewReason,
    ReviewStatus,
    ScrapeStatus,
    StockStatus,
    VendorTarget,
)
from src.infrastructure.playwright_fetcher import FetchResult, StaticPageDocument
from src.infrastructure.rate_limiter import HostRateLimiter
from src.infrastructure.robots import RobotsPolicy
from src.infrastructure.vendor_targets import (
    VendorTargetConfigError,
    merge_targets,
    parse_target,
)
from src.infrastructure.db.repositories.vendor_target import row_to_target
from src.services.vendor_confidence import DeltaReviewer
from src.services.vendor_scraper import VendorScrapeService

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "competitor_site"
FIXED_NOW = datetime(2026, 9, 27, 3, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class FakeFetcher:
    def __init__(self, results):
        self._results = results
        self.requested = []

    def fetch(self, url):
        self.requested.append(url)
        return self._results.get(url) or FetchResult(status=404)

    def close_page(self):
        pass

    def close(self):
        pass


class FakeObservationRepo:
    def __init__(self):
        self.inserted = []

    def latest_accepted(self, vendor, url):
        return None

    def insert(self, observation):
        self.inserted.append(observation)
        return len(self.inserted)


def robots(body="User-agent: *\nAllow: /\n"):
    return RobotsPolicy(user_agent="TestScraper/1.0", fetcher=lambda url: (200, body))


def instant_limiter():
    ticks = {"t": 0.0}

    def sleeper(seconds):
        ticks["t"] += seconds

    return HostRateLimiter(default_interval=0.0, clock=lambda: ticks["t"], sleeper=sleeper)


def service(fetcher, repo=None, robots_policy=None):
    return VendorScrapeService(
        fetcher=fetcher,
        robots=robots_policy or robots(),
        rate_limiter=instant_limiter(),
        reviewer=DeltaReviewer(min_confidence=0.6, delta_threshold=0.25),
        repository=repo,
        clock=lambda: FIXED_NOW,
    )


SELECTORS = FieldSelectors(
    price=(".product-price .amount",),
    stock=(".stock-status",),
    coa=("a.coa-link",),
    product_name=("h1.product-title",),
)


def product_doc(name, price, stock="In stock"):
    return StaticPageDocument(
        texts={
            "h1.product-title": name,
            ".product-price .amount": price,
            ".stock-status": stock,
        }
    )


# ---------------------------------------------------------------------------
# Target parsing and merging
# ---------------------------------------------------------------------------


class TestTargetParsing:
    def test_new_fields_round_trip(self):
        target = parse_target(
            {
                "slug": "rival",
                "name": "Rival Labs",
                "listing_url": "https://rival.example/shop",
                "listing_link_selector": "a.product-link",
                "platform_vendor_slug": " Rival-Labs ",
                "selectors": {"price": ".price"},
            },
            source="db",
        )
        assert target.listing_url == "https://rival.example/shop"
        assert target.listing_link_selector == "a.product-link"
        assert target.platform_vendor_slug == "rival-labs"
        assert target.source == "db"
        assert target.to_dict()["selectors"]["price"] == [".price"]

    def test_listing_url_without_link_selector_is_refused(self):
        with pytest.raises(VendorTargetConfigError, match="listing_link_selector"):
            parse_target({"slug": "rival", "listing_url": "https://rival.example/shop"})

    def test_relative_listing_url_is_refused(self):
        with pytest.raises(VendorTargetConfigError, match="absolute"):
            parse_target(
                {"slug": "rival", "listing_url": "/shop", "listing_link_selector": "a"}
            )

    def test_db_row_goes_through_the_same_validator(self):
        target = row_to_target(
            {
                "slug": "rival",
                "name": "Rival",
                "enabled": False,
                "product_urls": '["https://rival.example/p/1"]',
                "selectors": {"price": [".price"]},
                "min_request_interval_seconds": Decimal("7.50"),
                "max_products_per_run": 3,
            }
        )
        assert target.source == "db"
        assert target.enabled is False
        assert target.product_urls == ("https://rival.example/p/1",)
        assert target.min_request_interval_seconds == 7.5

    def test_merge_db_wins_even_when_disabled(self):
        db = [VendorTarget(slug="Rival", name="DB copy", enabled=False, source="db")]
        file = [
            VendorTarget(slug="rival", name="File copy", source="file"),
            VendorTarget(slug="other", name="Other", source="file"),
        ]
        merged = merge_targets(db, file, include_disabled=True)
        assert [(t.slug, t.source) for t in merged] == [("Rival", "db"), ("other", "file")]
        # Disabled in the DB means paused, even though the file enables it.
        enabled = merge_targets(db, file)
        assert [t.slug for t in enabled] == ["other"]


# ---------------------------------------------------------------------------
# Listing discovery and progress
# ---------------------------------------------------------------------------


LISTING = "https://rival.example/shop"


def listing_target(**overrides):
    defaults = dict(
        slug="rival",
        name="Rival",
        product_urls=("https://rival.example/p/configured",),
        listing_url=LISTING,
        listing_link_selector="a.product-link",
        selectors=SELECTORS,
        currency="USD",
    )
    defaults.update(overrides)
    return VendorTarget(**defaults)


class TestListingDiscovery:
    def test_discovers_same_host_links_deduped_and_defragmented(self):
        fetcher = FakeFetcher(
            {
                LISTING: FetchResult(
                    status=200,
                    document=StaticPageDocument(
                        attr_lists={
                            "a.product-link": {
                                "href": [
                                    "/p/a",
                                    "p/b",  # relative to /shop -> /p/b
                                    "/p/a#reviews",  # same page, fragment dropped
                                    "https://elsewhere.example/p/x",  # other host: never
                                    "mailto:sales@rival.example",
                                    "https://rival.example/p/configured",  # already configured
                                ]
                            }
                        }
                    ),
                ),
                "https://rival.example/p/configured": FetchResult(status=200, document=product_doc("BPC-157 5mg", "$39.00")),
                "https://rival.example/p/a": FetchResult(status=200, document=product_doc("TB-500 10mg", "$89.50")),
                "https://rival.example/p/b": FetchResult(status=200, document=product_doc("9-Me-BC 10mg", "$54.99")),
            }
        )
        report = service(fetcher).run([listing_target()])

        urls = [o.url for o in report.observations]
        assert urls == [
            "https://rival.example/p/configured",
            "https://rival.example/p/a",
            "https://rival.example/p/b",
        ]
        assert "https://elsewhere.example/p/x" not in fetcher.requested
        assert all(o.status is ScrapeStatus.OK for o in report.observations)

    def test_robots_disallowed_listing_is_recorded_and_never_fetched(self):
        fetcher = FakeFetcher(
            {"https://rival.example/p/configured": FetchResult(status=200, document=product_doc("BPC-157 5mg", "$39.00"))}
        )
        repo = FakeObservationRepo()
        report = service(
            fetcher, repo, robots("User-agent: *\nDisallow: /shop\n")
        ).run([listing_target()])

        assert LISTING not in fetcher.requested
        statuses = {o.url: o.status for o in report.observations}
        assert statuses[LISTING] is ScrapeStatus.ROBOTS_DISALLOWED
        # The configured product URL still runs.
        assert statuses["https://rival.example/p/configured"] is ScrapeStatus.OK
        assert len(repo.inserted) == 2

    def test_cap_applies_after_discovery(self):
        fetcher = FakeFetcher(
            {
                LISTING: FetchResult(
                    status=200,
                    document=StaticPageDocument(attr_lists={"a.product-link": {"href": ["/p/a", "/p/b", "/p/c"]}}),
                ),
            }
        )
        report = service(fetcher).run([listing_target(max_products_per_run=2)])
        assert len(report.observations) == 2

    def test_progress_reports_real_totals(self):
        fetcher = FakeFetcher(
            {
                "https://a.example/1": FetchResult(status=200, document=product_doc("BPC-157 5mg", "$39.00")),
                "https://a.example/2": FetchResult(status=200, document=product_doc("TB-500 10mg", "$89.50")),
            }
        )
        calls = []
        target = VendorTarget(
            slug="a",
            name="A",
            product_urls=("https://a.example/1", "https://a.example/2"),
            selectors=SELECTORS,
        )
        service(fetcher).run([target], on_progress=lambda done, total: calls.append((done, total)))
        assert calls == [(0, 2), (1, 2), (2, 2)]

    def test_a_broken_progress_callback_never_ends_the_run(self):
        fetcher = FakeFetcher(
            {"https://a.example/1": FetchResult(status=200, document=product_doc("BPC-157 5mg", "$39.00"))}
        )
        target = VendorTarget(slug="a", name="A", product_urls=("https://a.example/1",), selectors=SELECTORS)

        def boom(done, total):
            raise RuntimeError("ui went away")

        report = service(fetcher).run([target], on_progress=boom)
        assert report.observations[0].status is ScrapeStatus.OK


# ---------------------------------------------------------------------------
# Endpoints (called directly — no HTTP client dependency, no lifespan)
# ---------------------------------------------------------------------------


class FakeTargetRepo:
    def __init__(self, targets=None):
        self.targets = {t.slug.lower(): t for t in (targets or [])}
        self.connection = type("C", (), {"close": lambda self: None})()

    def list_all(self):
        return list(self.targets.values())

    def get(self, slug):
        return self.targets.get(slug.lower())

    def create(self, target):
        self.targets[target.slug.lower()] = target
        return target

    def update(self, slug, target):
        if slug.lower() not in self.targets:
            return None
        self.targets[slug.lower()] = target
        return target

    def delete(self, slug):
        return 1 if self.targets.pop(slug.lower(), None) else 0


class FakeObsRepo:
    def __init__(self, rows):
        self.rows = rows
        self.connection = type("C", (), {"close": lambda self: None})()

    def get_row(self, observation_id):
        return next((r for r in self.rows if r["id"] == observation_id), None)

    def resolve_review(self, observation_id, status, reviewer=None):
        row = self.get_row(observation_id)
        if not row or row["review_status"] != "flagged":
            return 0
        if status is ReviewStatus.ACCEPTED and row["price"] is None:
            return 0
        row["review_status"] = status.value
        return 1

    def list_latest_accepted(self, vendor=None):
        return [dict(r) for r in self.rows if r["review_status"] == "accepted" and (vendor is None or r["vendor"] == vendor)]

    def list_observations(self, **kwargs):
        rows = [r for r in self.rows if not kwargs.get("review_status") or r["review_status"] == kwargs["review_status"]]
        return {"total": len(rows), "rows": rows}


@pytest.fixture
def api(monkeypatch):
    import src.api.v1.endpoints.vendors as vendors
    import src.services.vendor_scrape_runner as runner

    target_repo = FakeTargetRepo()
    obs_repo = FakeObsRepo(
        [
            {"id": 1, "vendor": "rival", "url": "https://rival.example/p/1", "price": Decimal("39.00"), "review_status": "accepted"},
            {"id": 2, "vendor": "rival", "url": "https://rival.example/p/2", "price": None, "review_status": "flagged"},
            {"id": 3, "vendor": "rival", "url": "https://rival.example/p/3", "price": Decimal("12.00"), "review_status": "flagged"},
        ]
    )
    monkeypatch.setattr(vendors, "_target_repository", lambda: target_repo)
    monkeypatch.setattr(vendors, "_repository", lambda: obs_repo)
    monkeypatch.setattr(runner, "load_db_targets", lambda: target_repo.list_all())
    monkeypatch.setattr(runner, "load_targets", lambda include_disabled=False: [])
    # Saving a target resolves its host (SSRF guard). Keep these tests offline:
    # the *.example hosts used here "resolve" to a fixed public address
    # instead of going to a real resolver.
    import src.infrastructure.url_safety as url_safety

    monkeypatch.setattr(url_safety, "_system_resolver", lambda host: ["93.184.216.34"])
    return vendors, target_repo, obs_repo


def run(coro):
    return asyncio.run(coro)


def payload(vendors, **overrides):
    data = dict(
        slug="rival",
        name="Rival Labs",
        product_urls=["https://rival.example/p/1"],
        selectors={"price": [".price"]},
        platform_vendor_slug="rival-labs",
    )
    data.update(overrides)
    return vendors.TargetPayload(**data)


class TestTargetEndpoints:
    def test_create_list_update_delete(self, api):
        vendors, repo, _ = api
        created = run(vendors.create_vendor_target(payload(vendors)))
        assert created["source"] == "db" and created["platform_vendor_slug"] == "rival-labs"

        listed = run(vendors.list_vendor_targets())
        assert listed["count"] == 1 and listed["targets"][0]["slug"] == "rival"

        updated = run(vendors.update_vendor_target("rival", payload(vendors, enabled=False, name="Rival 2")))
        assert updated["enabled"] is False and updated["name"] == "Rival 2"

        response = run(vendors.delete_vendor_target("rival"))
        assert response.status_code == 204
        assert repo.targets == {}

    def test_duplicate_create_is_409(self, api):
        vendors, _, _ = api
        run(vendors.create_vendor_target(payload(vendors)))
        with pytest.raises(HTTPException) as exc:
            run(vendors.create_vendor_target(payload(vendors)))
        assert exc.value.status_code == 409

    def test_target_without_price_selector_or_urls_is_422(self, api):
        vendors, _, _ = api
        with pytest.raises(HTTPException) as exc:
            run(vendors.create_vendor_target(payload(vendors, selectors={"price": []})))
        assert exc.value.status_code == 422
        with pytest.raises(HTTPException) as exc:
            run(vendors.create_vendor_target(payload(vendors, product_urls=[])))
        assert exc.value.status_code == 422

    def test_slug_is_immutable(self, api):
        vendors, _, _ = api
        with pytest.raises(HTTPException) as exc:
            run(vendors.update_vendor_target("rival", payload(vendors, slug="other")))
        assert exc.value.status_code == 422

    def test_scrape_refuses_a_second_concurrent_run(self, api, monkeypatch):
        vendors, _, _ = api
        from fastapi import BackgroundTasks
        from src.core.job_queue import get_job_queue

        run(vendors.create_vendor_target(payload(vendors)))
        job = get_job_queue().create_job(vendors.SCRAPE_JOB_ENDPOINT, {})
        job.start()
        try:
            with pytest.raises(HTTPException) as exc:
                run(vendors.trigger_vendor_scrape(vendors.VendorScrapeRequest(), BackgroundTasks()))
            assert exc.value.status_code == 409
        finally:
            job.complete({})

    def test_scrape_job_reports_progress(self, api, monkeypatch):
        vendors, _, _ = api
        from src.core.job_queue import get_job_queue

        def fake_run(vendors=None, limit_per_vendor=None, on_progress=None):
            on_progress(1, 4)
            on_progress(4, 4)
            return {"urls_processed": 4, "review_counts": {"accepted": 4}, "observations": []}

        monkeypatch.setattr(vendors, "run_vendor_scrape", fake_run)
        job = get_job_queue().create_job(vendors.SCRAPE_JOB_ENDPOINT, {})
        vendors._run_scrape_task(job.job_id, ["rival"], None)
        view = run(vendors.get_vendor_scrape_job(job.job_id))
        assert view["status"] == "completed"
        assert view["progress"] == 100
        assert view["progress_detail"] == {"done": 4, "total": 4}


class TestObservationEndpoints:
    def test_accepted_latest_carries_platform_vendor_slug(self, api):
        vendors, _, _ = api
        run(vendors.create_vendor_target(payload(vendors)))
        body = run(vendors.list_latest_accepted_observations(vendor=None))
        assert body["count"] == 1
        assert body["observations"][0]["platform_vendor_slug"] == "rival-labs"
        assert body["observations"][0]["vendor_name"] == "Rival Labs"

    def test_accepting_a_priceless_reading_is_409(self, api):
        vendors, _, _ = api
        with pytest.raises(HTTPException) as exc:
            run(vendors.review_observation(2, vendors.ReviewRequest(decision="accept")))
        assert exc.value.status_code == 409
        # Rejecting it is fine.
        result = run(vendors.review_observation(2, vendors.ReviewRequest(decision="reject")))
        assert result["review_status"] == "rejected"

    def test_review_twice_is_409_and_unknown_is_404(self, api):
        vendors, _, _ = api
        run(vendors.review_observation(3, vendors.ReviewRequest(decision="accept")))
        with pytest.raises(HTTPException) as exc:
            run(vendors.review_observation(3, vendors.ReviewRequest(decision="reject")))
        assert exc.value.status_code == 409
        with pytest.raises(HTTPException) as exc:
            run(vendors.review_observation(99, vendors.ReviewRequest(decision="accept")))
        assert exc.value.status_code == 404

    def test_observation_filters_are_validated(self, api):
        vendors, _, _ = api
        with pytest.raises(HTTPException) as exc:
            run(vendors.list_observations(vendor=None, review_status="maybe", status=None, limit=50, offset=0))
        assert exc.value.status_code == 422
        body = run(vendors.list_observations(vendor=None, review_status="flagged", status=None, limit=50, offset=0))
        assert body["total"] == 2


# ---------------------------------------------------------------------------
# Local fixture HTTP server + the real Playwright fetcher
# ---------------------------------------------------------------------------


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    requested = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        type(self).requested.append(self.path)
        super().do_GET()


@pytest.fixture
def fixture_site():
    _QuietHandler.requested = []
    handler = functools.partial(_QuietHandler, directory=str(FIXTURE_ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", _QuietHandler.requested
    finally:
        server.shutdown()
        server.server_close()


def _playwright_fetcher_or_skip():
    import os

    from src.infrastructure.playwright_fetcher import PlaywrightPageFetcher

    fetcher = PlaywrightPageFetcher(user_agent="PeptidesVendorScraper/test (+local fixture)", timeout_ms=15000)
    try:
        fetcher._ensure_started()
    except Exception as exc:  # noqa: BLE001
        fetcher.close()
        pytest.skip(f"no launchable Chromium (set CHROME_BIN): {exc}  CHROME_BIN={os.environ.get('CHROME_BIN')}")
    return fetcher


class TestLocalFixtureSite:
    def test_end_to_end_against_the_fixture_site(self, fixture_site, monkeypatch):
        from src.config import settings

        # The fixture site is on 127.0.0.1, which the SSRF guard refuses by
        # default: opt in explicitly, for this test only.
        monkeypatch.setattr(settings, "VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS", True)
        base, requested = fixture_site
        fetcher = _playwright_fetcher_or_skip()
        repo = FakeObservationRepo()
        target = VendorTarget(
            slug="fixture-shop",
            name="Fixture Peptide Shop",
            listing_url=f"{base}/index.html",
            listing_link_selector="a.product-link",
            selectors=SELECTORS,
            currency="USD",
            min_request_interval_seconds=0.0,
        )
        svc = VendorScrapeService(
            fetcher=fetcher,
            robots=RobotsPolicy(user_agent="PeptidesVendorScraper/test"),
            rate_limiter=HostRateLimiter(default_interval=0.0),
            reviewer=DeltaReviewer(min_confidence=0.6, delta_threshold=0.25),
            repository=repo,
        )
        report = svc.run([target])
        by_path = {o.url.replace(base, ""): o for o in report.observations}

        # robots.txt was read, and /private/ was never requested.
        assert "/robots.txt" in requested
        assert not any(p.startswith("/private/") for p in requested)
        assert by_path["/private/secret.html"].status is ScrapeStatus.ROBOTS_DISALLOWED
        # The off-host partner link was ignored entirely.
        assert not any("elsewhere.invalid" in o.url for o in report.observations)

        nine = by_path["/products/9-me-bc-10mg.html"]
        assert nine.product_name == "9-Me-BC 10mg x 60 capsules"
        assert nine.price == Decimal("54.99") and nine.currency == "USD"
        assert nine.stock_status is StockStatus.IN_STOCK
        assert nine.coa_url == f"{base}/coa/9-me-bc-lot-2291.pdf"
        assert nine.review_status is ReviewStatus.ACCEPTED

        tb = by_path["/products/tb-500-10mg.html"]
        assert tb.price == Decimal("89.50") and tb.stock_status is StockStatus.OUT_OF_STOCK

        no_price = by_path["/products/no-price.html"]
        assert no_price.price is None
        assert no_price.review_status is ReviewStatus.FLAGGED
        assert no_price.review_reason is ReviewReason.NO_PRICE

        # Every reading (including the robots refusal) was persisted.
        assert len(repo.inserted) == len(report.observations)
