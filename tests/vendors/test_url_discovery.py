"""Selector-free competitor discovery (AAD-1): store URL in, priced variants out.

Offline: every HTTP response is replayed from ``fixtures/url_discovery``
through an injected transport, robots.txt comes from an injected fetcher, and
the rate limiter's clock and sleep are fake. No test reaches the network.
"""

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.vendor_models import (
    ScrapeStatus,
    StockStatus,
    TargetReviewState,
    VendorTarget,
)
from app.infrastructure.polite_http import HttpResult, PoliteHttpClient
from app.infrastructure.rate_limiter import HostRateLimiter
from app.infrastructure.robots import RobotsPolicy
from app.scrapers.vendors.extractors.store_api import (
    looks_like_product_url,
    parse_sitemap,
    rank_child_sitemaps,
    woo_price,
)
from app.scrapers.vendors.extractors.structured_data import parse_product_page
from app.scrapers.vendors.extractors.value_parsing import compose_name, to_price
from app.scrapers.vendors.url_discovery import UrlOnlyDiscovery
from app.scrapers.vendors.vendor_confidence import DeltaReviewer
from app.scrapers.vendors.vendor_scraper import VendorScrapeService

FIXTURES = Path(__file__).parent / "fixtures" / "url_discovery"
ORIGIN = "https://rival.example"
API = f"{ORIGIN}/wp-json/wc/store/v1/products"
FIXED_NOW = datetime(2026, 10, 14, 3, 15, tzinfo=UTC)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class ReplayTransport:
    """``url -> HttpResult`` from a dict; anything else is a 404. Records calls."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.headers_seen = []

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        self.headers_seen.append(dict(headers))
        route = self.routes.get(url)
        if route is None:
            return HttpResult(url=url, status=404, text="<html>not found</html>")
        if isinstance(route, HttpResult):
            return HttpResult(url=url, status=route.status, text=route.text, headers=dict(route.headers))
        status, body, headers_out = route if len(route) == 3 else (*route, {})
        return HttpResult(url=url, status=status, text=body, headers={k.lower(): v for k, v in headers_out.items()})


def ok(body, **headers):
    return (200, body, headers)


def robots_policy(body="User-agent: *\nAllow: /\n", status=200):
    return RobotsPolicy(user_agent="TestScraper/1.0", fetcher=lambda url: (status, body))


def limiter():
    ticks = {"t": 0.0}

    def sleeper(seconds):
        ticks["t"] += seconds

    return HostRateLimiter(default_interval=0.0, base_backoff=0.0, clock=lambda: ticks["t"], sleeper=sleeper)


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    # The SSRF guard resolves every host; *.example "resolves" publicly here.
    from app.infrastructure import url_safety

    monkeypatch.setattr(url_safety, "_system_resolver", lambda host: ["93.184.216.34"])


def discovery(routes, *, robots=None, max_requests=60, max_products=200, renderer=None, concurrency=2):
    transport = ReplayTransport(routes)
    client = PoliteHttpClient(
        robots or robots_policy(),
        limiter(),
        transport=transport,
        max_requests=max_requests,
        concurrency=concurrency,
    )
    return UrlOnlyDiscovery(client, renderer=renderer, max_products=max_products), transport, client


WOO_ROUTES = {
    f"{API}?per_page=2&page=1": ok(fixture("woo_products_page1.json"), **{"X-WP-TotalPages": "2"}),
    f"{API}?per_page=2&page=2": ok(fixture("woo_products_page2.json"), **{"X-WP-TotalPages": "2"}),
    f"{API}?per_page=100&page=1": ok(
        json.dumps(json.loads(fixture("woo_products_page1.json")) + json.loads(fixture("woo_products_page2.json")))
    ),
    f"{API}?type=variation&per_page=100&include=203,204": ok(fixture("woo_variations.json")),
}


# ---------------------------------------------------------------------------
# WooCommerce Store API
# ---------------------------------------------------------------------------


class TestWooStoreApi:
    def test_paginates_and_reads_one_reading_per_variant(self):
        disc, transport, _ = discovery(WOO_ROUTES, max_products=2)
        result = disc.discover(f"{ORIGIN}/")

        assert result.method == "woo_store_api"
        # page size 2 -> two pages, then one batched variations call
        assert f"{API}?per_page=2&page=1" in transport.calls
        assert f"{API}?per_page=2&page=2" not in transport.calls  # capped at 2 products
        by_name = {r.product_name: r for r in result.readings}
        assert set(by_name) == {"BPC-157 – 5mg", "Retatrutide 10mg", "Retatrutide 20mg"}

        simple = by_name["BPC-157 – 5mg"]
        assert simple.price == Decimal("39.99") and simple.currency == "USD"
        assert simple.stock_status is StockStatus.IN_STOCK

        ten = by_name["Retatrutide 10mg"]
        twenty = by_name["Retatrutide 20mg"]
        assert ten.price == Decimal("89.00") and ten.variant_label == "10mg" and ten.sku == "RETA-10"
        assert twenty.price == Decimal("159.00") and twenty.stock_status is StockStatus.ON_BACKORDER
        # Each size has its own key, so the review gate never compares 10mg with 20mg.
        assert ten.url != twenty.url
        assert all(r.confidence >= 0.9 for r in result.readings)

    def test_follows_pages_until_total_pages(self, monkeypatch):
        from app.scrapers.vendors import url_discovery

        monkeypatch.setattr(url_discovery, "WOO_PAGE_SIZE", 2)
        routes = dict(WOO_ROUTES)
        routes[f"{API}?type=variation&per_page=2&include=203,204"] = ok(fixture("woo_variations.json"))
        disc, transport, _ = discovery(routes, max_products=10)
        result = disc.discover(ORIGIN)
        assert transport.calls[:2] == [f"{API}?per_page=2&page=1", f"{API}?per_page=2&page=2"]
        assert result.products_seen == 3
        assert len(result.readings) == 4  # 2 simple + 2 sizes

    def test_stops_at_a_short_page(self):
        routes = dict(WOO_ROUTES)
        routes[f"{API}?per_page=100&page=1"] = ok(fixture("woo_products_page1.json"), **{"X-WP-TotalPages": "2"})
        routes[f"{API}?per_page=100&page=2"] = ok(fixture("woo_products_page2.json"), **{"X-WP-TotalPages": "2"})
        disc, transport, _ = discovery(routes)
        result = disc.discover(f"{ORIGIN}/shop/")
        # page 1 returned fewer than per_page items, so the loop stops there.
        assert result.products_seen == 2
        assert f"{API}?per_page=100&page=2" not in transport.calls

    def test_out_of_stock_simple_product(self):
        disc, _, _ = discovery(WOO_ROUTES)
        result = disc.discover(ORIGIN)
        tb = next(r for r in result.readings if r.product_name == "TB-500 10mg")
        assert tb.stock_status is StockStatus.OUT_OF_STOCK and tb.price == Decimal("65.00")

    def test_product_url_reads_only_that_product_by_slug(self):
        routes = {
            f"{API}?slug=retatrutide": ok(json.dumps([json.loads(fixture("woo_products_page1.json"))[1]])),
            f"{API}?type=variation&per_page=100&include=203,204": ok(fixture("woo_variations.json")),
        }
        disc, transport, _ = discovery(routes)
        result = disc.discover(f"{ORIGIN}/product/retatrutide/")
        assert result.method == "woo_store_api" and result.products_seen == 1
        assert sorted(r.variant_label for r in result.readings) == ["10mg", "20mg"]
        assert len(transport.calls) == 2

    def test_variable_product_without_readable_sizes_keeps_from_price_for_review(self):
        # The variations call is not answered (404): the sizes stay unknown.
        variable_only = json.dumps([json.loads(fixture("woo_products_page1.json"))[1]])
        disc, _, _ = discovery({f"{API}?per_page=100&page=1": ok(variable_only)})
        result = disc.discover(ORIGIN)
        assert len(result.readings) == 1
        reading = result.readings[0]
        assert reading.price == Decimal("89.00")
        assert reading.confidence < 0.6  # a range is flagged, never auto-accepted

    def test_minor_units(self):
        assert woo_price({"price": "1250", "currency_minor_unit": 2, "currency_code": "usd"}) == (
            Decimal("12.50"),
            "USD",
        )
        assert woo_price({"price": "1250", "currency_minor_unit": 0, "currency_code": "JPY"}) == (Decimal(1250), "JPY")
        assert woo_price({"price": "0", "currency_minor_unit": 2}) == (None, None)


# ---------------------------------------------------------------------------
# Shopify
# ---------------------------------------------------------------------------


class TestShopify:
    def test_products_json_paginates_and_reads_variants(self):
        routes = {f"{ORIGIN}/products.json?limit=250&page=1": ok(fixture("shopify_products.json"))}
        disc, transport, _ = discovery(routes, max_products=500)
        disc._currency = "USD"
        result = disc.discover(ORIGIN)

        assert result.method == "shopify_json"
        # The Woo probe went first and 404'd; Shopify answered.
        assert transport.calls[0].startswith(API)
        names = {r.product_name: r for r in result.readings}
        assert set(names) == {"Semaglutide 5mg", "Semaglutide 10mg", "BAC Water 10ml"}
        assert names["Semaglutide 10mg"].price == Decimal("129.50")
        assert names["Semaglutide 10mg"].stock_status is StockStatus.OUT_OF_STOCK
        assert names["Semaglutide 5mg"].url == f"{ORIGIN}/products/semaglutide?variant=41001"
        # "Default Title" is Shopify's placeholder, not a size.
        assert names["BAC Water 10ml"].variant_label is None
        assert names["BAC Water 10ml"].url == f"{ORIGIN}/products/bac-water-10ml"
        assert all(r.currency == "USD" for r in result.readings)

    def test_second_page_requested_when_first_is_full(self):
        products = json.loads(fixture("shopify_products.json"))["products"]
        routes = {
            f"{ORIGIN}/products.json?limit=2&page=1": ok(json.dumps({"products": products})),
            f"{ORIGIN}/products.json?limit=2&page=2": ok(json.dumps({"products": []})),
        }
        disc, transport, _ = discovery(routes, max_products=2)
        result = disc.discover(ORIGIN)
        assert result.products_seen == 2
        assert f"{ORIGIN}/products.json?limit=2&page=2" not in transport.calls  # cap reached

    def test_product_url_uses_handle_json(self):
        product = json.loads(fixture("shopify_products.json"))["products"][0]
        routes = {f"{ORIGIN}/products/semaglutide.json": ok(json.dumps({"product": product}))}
        disc, transport, _ = discovery(routes)
        result = disc.discover(f"{ORIGIN}/products/semaglutide")
        assert result.method == "shopify_json"
        assert [r.variant_label for r in result.readings] == ["5mg", "10mg"]
        assert transport.calls == [f"{ORIGIN}/products/semaglutide.json"]


# ---------------------------------------------------------------------------
# Sitemaps + structured data
# ---------------------------------------------------------------------------


SITEMAP_ROUTES = {
    f"{ORIGIN}/sitemap_index.xml": ok(fixture("sitemap_index.xml")),
    f"{ORIGIN}/product-sitemap.xml": ok(fixture("product_sitemap.xml")),
    f"{ORIGIN}/product/ipamorelin/": ok(fixture("page_jsonld_offers.html")),
    f"{ORIGIN}/product/ghk-cu/": ok(fixture("page_jsonld_productgroup.html")),
    f"{ORIGIN}/product/kpv/": ok(fixture("page_jsonld_aggregate.html")),
}


class TestSitemapDiscovery:
    def test_robots_sitemap_index_to_product_pages(self):
        disc, transport, _ = discovery(SITEMAP_ROUTES, robots=robots_policy(fixture("robots_sitemap.txt")))
        result = disc.discover(ORIGIN)

        assert result.method == "sitemap"
        # robots.txt disallows /wp-json/: the Store API was never requested.
        assert not any("/wp-json/" in c for c in transport.calls)
        assert any("disallowed by robots.txt" in n for n in result.notes)
        # post/page/category sitemaps skipped; other hosts and /shop/ ignored.
        assert f"{ORIGIN}/post-sitemap.xml" not in transport.calls
        assert f"{ORIGIN}/product_cat-sitemap.xml" not in transport.calls
        assert not any("elsewhere.example" in c for c in transport.calls)
        assert result.products_seen == 3

        names = {r.product_name: r for r in result.readings}
        assert names["Ipamorelin 5mg"].price == Decimal("34.99")
        assert names["Ipamorelin 10mg"].price == Decimal("59.0")
        assert names["Ipamorelin 10mg"].stock_status is StockStatus.OUT_OF_STOCK
        assert names["GHK-Cu 50mg"].currency == "EUR"
        assert names["GHK-Cu 100mg"].price == Decimal("79.90")
        assert names["GHK-Cu 100mg"].stock_status is StockStatus.ON_BACKORDER
        assert names["KPV"].confidence < 0.6  # price range: flagged for a human

    def test_plain_sitemap_xml_fallback(self):
        routes = {
            f"{ORIGIN}/sitemap.xml": ok(fixture("product_sitemap.xml")),
            f"{ORIGIN}/product/ipamorelin/": ok(fixture("page_jsonld_offers.html")),
        }
        disc, _, _ = discovery(routes)
        result = disc.discover(ORIGIN)
        assert result.method == "sitemap"
        assert {r.variant_label for r in result.readings} == {"5mg", "10mg"}
        assert {f.url for f in result.failures} == {f"{ORIGIN}/product/ghk-cu/", f"{ORIGIN}/product/kpv/"}

    def test_parse_sitemap_shapes(self):
        kind, locs = parse_sitemap(fixture("sitemap_index.xml"))
        assert kind == "index" and len(locs) == 4
        assert rank_child_sitemaps(locs) == [f"{ORIGIN}/product-sitemap.xml"]
        assert parse_sitemap("<html>nope</html>") == (None, [])
        assert parse_sitemap('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><urlset/>') == (None, [])

    def test_product_url_shapes(self):
        assert looks_like_product_url(f"{ORIGIN}/product/bpc-157/")
        assert looks_like_product_url(f"{ORIGIN}/products/semaglutide")
        assert not looks_like_product_url(f"{ORIGIN}/product-category/peptides/")
        assert not looks_like_product_url(f"{ORIGIN}/shop/")
        assert not looks_like_product_url(f"{ORIGIN}/")


class TestStructuredData:
    def test_json_ld_offers_with_size_labels(self):
        readings = parse_product_page(fixture("page_jsonld_offers.html"), f"{ORIGIN}/product/ipamorelin/")
        assert [(r.product_name, r.variant_label, r.sku) for r in readings] == [
            ("Ipamorelin 5mg", "5mg", "IPA-5"),
            ("Ipamorelin 10mg", "10mg", "IPA-10"),
        ]
        assert all(r.method == "json_ld" and r.confidence == 0.9 for r in readings)
        assert len({r.url for r in readings}) == 2

    def test_product_group_variants_and_bad_block_ignored(self):
        readings = parse_product_page(fixture("page_jsonld_productgroup.html"), f"{ORIGIN}/product/ghk-cu/")
        assert [(r.variant_label, r.price) for r in readings] == [
            ("50mg", Decimal("45.00")),
            ("100mg", Decimal("79.90")),
        ]

    def test_microdata_then_opengraph(self):
        micro = parse_product_page(fixture("page_microdata.html"), f"{ORIGIN}/p/selank")
        assert len(micro) == 1
        assert (micro[0].product_name, micro[0].price, micro[0].currency, micro[0].method) == (
            "Selank 10mg",
            Decimal("42.50"),
            "GBP",
            "microdata",
        )
        assert micro[0].stock_status is StockStatus.IN_STOCK
        og = parse_product_page(fixture("page_opengraph.html"), f"{ORIGIN}/p/semax")
        assert (og[0].product_name, og[0].price, og[0].method) == ("Semax 30mg", Decimal("55.00"), "opengraph")
        assert og[0].confidence >= 0.6

    def test_no_price_is_nothing_not_zero(self):
        assert parse_product_page(fixture("page_no_price.html"), f"{ORIGIN}/p/x") == []
        assert to_price("0") is None
        assert to_price("0.00") is None
        assert to_price("250000") is None  # implausible: a phone number or a typo
        assert to_price("1.234,56") == Decimal("1234.56")
        assert to_price("1,234.56") == Decimal("1234.56")

    def test_compose_name_does_not_repeat_the_size(self):
        assert compose_name("Retatrutide", "10mg") == "Retatrutide 10mg"
        assert compose_name("Retatrutide 10MG", "10mg") == "Retatrutide 10MG"
        assert compose_name("BAC Water", "Default Title") == "BAC Water"


class TestSizeless:
    def test_a_price_with_no_size_is_held_for_review(self):
        # glpeptides.is publishes one Offer (the default size) on a multi-size page.
        page = (
            '<script type="application/ld+json">{"@type":"Product","name":"Retatrutide",'
            '"offers":{"@type":"Offer","price":"49.99","priceCurrency":"USD"}}</script>'
        )
        disc, _, _ = discovery({f"{ORIGIN}/item/reta": ok(page)})
        result = disc.read_product(f"{ORIGIN}/item/reta")
        assert result.readings[0].price == Decimal("49.99")
        assert result.readings[0].confidence < 0.6
        assert any("no size" in n for n in result.notes)

    def test_a_size_in_the_name_is_enough(self):
        page = (
            '<script type="application/ld+json">{"@type":"Product","name":"Retatrutide 10 mg",'
            '"offers":{"@type":"Offer","price":"49.99","priceCurrency":"USD"}}</script>'
        )
        disc, _, _ = discovery({f"{ORIGIN}/item/reta": ok(page)})
        assert disc.read_product(f"{ORIGIN}/item/reta").readings[0].confidence == 0.9


class TestRenderingFallback:
    def test_page_without_structured_price_is_rendered_once(self):
        from app.infrastructure.page_models import (
            FetchResult,
            StaticPageDocument,
        )

        class Renderer:
            def __init__(self):
                self.rendered = []

            def fetch_rendered(self, url):
                self.rendered.append(url)
                return FetchResult(status=200, document=StaticPageDocument(raw_html=fixture("page_opengraph.html")))

            def close_page(self):
                pass

        renderer = Renderer()
        routes = {f"{ORIGIN}/item/semax": ok(fixture("page_no_price.html"))}
        disc, _, client = discovery(routes, renderer=renderer)
        result = disc.read_product(f"{ORIGIN}/item/semax")
        assert renderer.rendered == [f"{ORIGIN}/item/semax"]
        assert result.readings[0].price == Decimal("55.00")
        assert client.requests_made == 2  # the rendered fetch spends budget too


# ---------------------------------------------------------------------------
# Politeness
# ---------------------------------------------------------------------------


class TestPoliteness:
    def test_robots_disallowed_product_page_is_never_fetched(self):
        robots = robots_policy("User-agent: *\nDisallow: /product/\n")
        disc, transport, _ = discovery(SITEMAP_ROUTES, robots=robots)
        result = disc.read_product(f"{ORIGIN}/product/ipamorelin/")
        assert f"{ORIGIN}/product/ipamorelin/" not in transport.calls
        assert result.failures and result.failures[0].status is ScrapeStatus.ROBOTS_DISALLOWED

    def test_unknown_robots_means_nothing_is_fetched(self):
        disc, transport, _ = discovery(WOO_ROUTES, robots=robots_policy("", status=503))
        result = disc.discover(ORIGIN)
        assert transport.calls == []
        assert result.readings == []

    def test_request_budget_caps_a_run(self):
        disc, transport, client = discovery(SITEMAP_ROUTES, max_requests=3)
        result = disc.discover(ORIGIN)
        assert len(transport.calls) <= 3 and client.requests_made <= 3
        assert result.readings == []

    def test_honest_user_agent_and_redirects_rechecked(self, monkeypatch):
        routes = {
            f"{ORIGIN}/product/a/": (301, "", {"Location": "http://127.0.0.1/admin"}),
        }
        disc, transport, _ = discovery(routes)
        from app.infrastructure import url_safety

        def resolver(host):
            return ["127.0.0.1"] if host == "127.0.0.1" else ["93.184.216.34"]

        monkeypatch.setattr(url_safety, "_system_resolver", resolver)
        result = disc.read_product(f"{ORIGIN}/product/a/")
        assert transport.headers_seen[0]["User-Agent"] == "TestScraper/1.0"
        # The internal redirect target was refused before it was requested.
        assert "http://127.0.0.1/admin" not in transport.calls
        assert result.readings == []

    def test_a_refusal_ends_the_host_without_retrying(self):
        routes = {f"{ORIGIN}/sitemap_index.xml": (403, "no", {})}
        disc, transport, _ = discovery(routes)
        disc.discover(ORIGIN)
        # Woo probe 404, Shopify probe 404, robots sitemaps none, index 403 -> stop.
        assert transport.calls.count(f"{ORIGIN}/sitemap_index.xml") == 1
        assert f"{ORIGIN}/sitemap.xml" not in transport.calls

    def test_concurrency_is_clamped_to_four(self):
        client = PoliteHttpClient(robots_policy(), limiter(), transport=ReplayTransport({}), concurrency=12)
        assert client.concurrency == 4
        client = PoliteHttpClient(robots_policy(), limiter(), transport=ReplayTransport({}), concurrency=0)
        assert client.concurrency == 1


# ---------------------------------------------------------------------------
# The scrape run: drafts, owned stores, review gate
# ---------------------------------------------------------------------------


class FakeRepo:
    def __init__(self, previous=None):
        self.inserted = []
        self.previous = previous or {}

    def latest_accepted(self, vendor, url):
        return self.previous.get(url)

    def insert(self, observation):
        self.inserted.append(observation)
        return len(self.inserted)


class NoBrowser:
    def fetch(self, url):  # pragma: no cover — must never be called for auto targets
        raise AssertionError("the browser path must not run for a selector-free target")

    def close_page(self):
        pass

    def close(self):
        pass


def scrape_service(routes, repo=None):
    robots = robots_policy()
    lim = limiter()

    def factory(target, cap):
        client = PoliteHttpClient(robots, lim, transport=ReplayTransport(routes), max_requests=60)
        return UrlOnlyDiscovery(client, max_products=cap or 200, currency=target.currency)

    return VendorScrapeService(
        fetcher=NoBrowser(),
        robots=robots,
        rate_limiter=lim,
        reviewer=DeltaReviewer(min_confidence=0.6, delta_threshold=0.25),
        repository=repo,
        clock=lambda: FIXED_NOW,
        discovery_factory=factory,
    )


class TestScrapeRun:
    def test_approved_url_only_target_is_scraped_per_variant(self):
        repo = FakeRepo()
        target = VendorTarget(slug="rival", name="Rival", store_url=f"{ORIGIN}/")
        report = scrape_service(WOO_ROUTES, repo).run([target])
        assert len(report.observations) == 4
        assert all(o.extraction_method == "woo_store_api" for o in report.observations)
        assert {o.variant_label for o in report.observations} >= {"10mg", "20mg"}
        assert report.review_counts()["accepted"] == 4
        assert len(repo.inserted) == 4

    def test_draft_target_is_not_scraped(self):
        repo = FakeRepo()
        target = VendorTarget(slug="rival", name="Rival", store_url=f"{ORIGIN}/", review_state=TargetReviewState.DRAFT)
        report = scrape_service(WOO_ROUTES, repo).run([target])
        assert report.observations == [] and repo.inserted == []

    def test_owned_store_is_never_scraped(self):
        target = VendorTarget(slug="sneaky", name="x", store_url="https://www.ruo.bio/shop/")
        report = scrape_service(WOO_ROUTES).run([target])
        assert [o.status for o in report.observations] == [ScrapeStatus.SKIPPED]
        assert "own stores" in (report.observations[0].failure_detail or "")

    def test_big_move_on_a_variant_is_flagged(self):
        from app.core.vendor_models import ReviewStatus, VendorObservation

        ten_url = "https://rival.example/product/retatrutide/?attribute_pa_size=10mg"
        previous = VendorObservation(
            vendor="rival",
            url=ten_url,
            observed_at=FIXED_NOW,
            price=Decimal("40.00"),
            review_status=ReviewStatus.ACCEPTED,
            confidence=0.95,
        )
        report = scrape_service(WOO_ROUTES, FakeRepo({ten_url: previous})).run(
            [VendorTarget(slug="rival", name="Rival", store_url=ORIGIN)]
        )
        ten = next(o for o in report.observations if o.url == ten_url)
        assert ten.review_status is ReviewStatus.FLAGGED and ten.review_reason.value == "price_delta"

    def test_nothing_found_is_recorded_not_silent(self):
        report = scrape_service({}).run([VendorTarget(slug="rival", name="Rival", store_url=ORIGIN)])
        assert len(report.observations) == 1
        assert report.observations[0].status is ScrapeStatus.ERROR
        assert report.observations[0].price is None


# ---------------------------------------------------------------------------
# API: from-url, approve, owned refusal, pagination
# ---------------------------------------------------------------------------


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def api(monkeypatch):
    import app.services.vendor_scrape_runner as runner
    from app.api.v1.endpoints import vendors
    from tests.vendors.test_vendor_targets_api import FakeTargetRepo

    class ApprovingRepo(FakeTargetRepo):
        def approve(self, slug, approved_by=None):
            from dataclasses import replace

            current = self.targets.get(slug.lower())
            if current is None:
                return None
            updated = replace(
                current, review_state=TargetReviewState.APPROVED, approved_by=approved_by, approved_at=FIXED_NOW
            )
            self.targets[slug.lower()] = updated
            return updated

    repo = ApprovingRepo()
    import app.services.vendor_target_service as target_service

    monkeypatch.setattr(target_service, "_target_repository", lambda: repo)
    monkeypatch.setattr(runner, "load_db_targets", lambda: repo.list_all())
    monkeypatch.setattr(runner, "load_targets", lambda include_disabled=False: [])
    return vendors, repo


class TestUrlOnlyEndpoints:
    def test_from_url_creates_a_draft_competitor_target(self, api):
        vendors, _ = api
        created = run(vendors.create_target_from_url(vendors.FromUrlRequest(url="https://www.rival.example/shop/")))
        assert created["slug"] == "rival-example"
        assert created["review_state"] == "draft" and created["discovery_mode"] == "auto"
        assert created["kind"] == "competitor" and created["store_url"] == "https://www.rival.example/shop/"
        # Drafts are listed but never selected for a run.
        from app.services.vendor_scrape_runner import select_targets

        assert select_targets() == [] and select_targets(["rival-example"]) == []

        approved = run(vendors.approve_vendor_target("rival-example", vendors.ApproveRequest(approved_by="admin@x")))
        assert approved["review_state"] == "approved" and approved["approved_by"] == "admin@x"
        assert [t.slug for t in select_targets()] == ["rival-example"]

    def test_from_url_duplicate_is_409(self, api):
        vendors, _ = api
        run(vendors.create_target_from_url(vendors.FromUrlRequest(url="https://rival.example/")))
        with pytest.raises(HTTPException) as exc:
            run(vendors.create_target_from_url(vendors.FromUrlRequest(url="https://rival.example/shop")))
        assert exc.value.status_code == 409

    @pytest.mark.parametrize(
        "url", ["https://ruo.bio/", "https://www.arcanepeptides.com/product/x/", "https://shop.moglabs.bio"]
    )
    def test_owned_domains_are_refused(self, api, url):
        vendors, repo = api
        with pytest.raises(HTTPException) as exc:
            run(vendors.create_target_from_url(vendors.FromUrlRequest(url=url)))
        assert exc.value.status_code == 422 and "own store" in exc.value.detail
        with pytest.raises(HTTPException) as exc:
            run(vendors.discover_from_url(vendors.DiscoverRequest(url=url)))
        assert exc.value.status_code == 422
        assert repo.targets == {}

    def test_owned_slug_is_refused_on_create(self, api):
        vendors, _ = api
        with pytest.raises(HTTPException) as exc:
            run(
                vendors.create_vendor_target(
                    vendors.TargetPayload(slug="moglabs", name="x", store_url="https://rival.example/")
                )
            )
        assert exc.value.status_code == 422

    def test_internal_url_is_refused(self, api):
        vendors, _ = api
        with pytest.raises(HTTPException) as exc:
            run(vendors.create_target_from_url(vendors.FromUrlRequest(url="http://169.254.169.254/latest")))
        assert exc.value.status_code == 422

    def test_saving_a_draft_does_not_approve_it(self, api):
        vendors, _ = api
        run(vendors.create_target_from_url(vendors.FromUrlRequest(url="https://rival.example/")))
        updated = run(
            vendors.update_vendor_target(
                "rival-example",
                vendors.TargetPayload(slug="rival-example", name="Rival", store_url="https://rival.example/"),
            )
        )
        assert updated["review_state"] == "draft"

    def test_a_client_without_store_url_does_not_wipe_it(self, api):
        vendors, _ = api
        run(vendors.create_target_from_url(vendors.FromUrlRequest(url="https://rival.example/")))
        # Today's admin drawer sends no store_url; selectors added for an odd site.
        updated = run(
            vendors.update_vendor_target(
                "rival-example",
                vendors.TargetPayload(
                    slug="rival-example",
                    name="Rival",
                    product_urls=["https://rival.example/p/1"],
                    selectors={"price": [".price"]},
                ),
            )
        )
        assert updated["store_url"] == "https://rival.example/"
        assert updated["discovery_mode"] == "selectors" and updated["review_state"] == "draft"

    def test_targets_pagination_is_backwards_compatible(self, api):
        vendors, _ = api
        for i in range(5):
            run(
                vendors.create_vendor_target(
                    vendors.TargetPayload(
                        slug=f"rival-{i}",
                        name=f"Rival {i}",
                        product_urls=[f"https://rival{i}.example/p/1"],
                        selectors={"price": [".price"]},
                    )
                )
            )
        run(vendors.create_target_from_url(vendors.FromUrlRequest(url="https://other.example/")))

        everything = run(vendors.list_vendor_targets())
        assert everything["count"] == everything["total"] == 6 and everything["limit"] is None
        assert everything["draft_count"] == 1

        page = run(vendors.list_vendor_targets(limit=2, offset=2))
        assert page["total"] == 6 and page["count"] == 2
        assert [t["slug"] for t in page["targets"]] == [t["slug"] for t in everything["targets"][2:4]]

        drafts = run(vendors.list_vendor_targets(review_state="draft"))
        assert [t["slug"] for t in drafts["targets"]] == ["other-example"]
        searched = run(vendors.list_vendor_targets(q="rival3"))
        assert [t["slug"] for t in searched["targets"]] == ["rival-3"]
        with pytest.raises(HTTPException):
            run(vendors.list_vendor_targets(review_state="bogus"))

    def test_flagged_queue_paginates_with_total(self, api, monkeypatch):
        vendors, _ = api

        class Obs:
            connection = type("C", (), {"close": lambda self: None})()

            def list_flagged(self, limit, vendor=None, offset=0):
                rows = [{"id": i} for i in range(7)]
                return rows[offset : offset + limit]

            def count_flagged(self, vendor=None):
                return 7

        import app.services.vendor_observation_service as observation_service

        monkeypatch.setattr(observation_service, "_repository", lambda: Obs())
        default = run(vendors.list_flagged_observations(limit=50, vendor=None))
        assert default["count"] == 7 and default["total"] == 7 and default["offset"] == 0
        page = run(vendors.list_flagged_observations(limit=3, vendor=None, offset=6))
        assert page["count"] == 1 and page["total"] == 7

    def test_discover_preview_runs_offline(self, api, monkeypatch):
        vendors, _ = api
        import app.services.vendor_scrape_runner as runner

        seen = {}

        def fake_preview(url, max_products, currency):
            seen.update(url=url, max_products=max_products)
            return {"seed_url": url, "method": "woo_store_api", "readings": []}

        import app.services.vendor_target_service as target_service

        monkeypatch.setattr(target_service, "preview_discovery", fake_preview)
        out = run(vendors.discover_from_url(vendors.DiscoverRequest(url="https://rival.example/", max_products=3)))
        assert out["method"] == "woo_store_api" and seen == {"url": "https://rival.example/", "max_products": 3}
        assert runner.preview_discovery is not None
