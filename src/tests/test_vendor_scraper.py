"""Tests for competitor vendor scraping (peptides-platform#288).

No network, no browser, no database. Playwright is never imported: the
service takes a :class:`~src.infrastructure.playwright_fetcher.PageFetcher`,
and these tests pass a fake one. Every robots.txt response is canned, every
clock and sleeper is injected, and the repository is an in-memory double.

The tests that matter most are the guard tests — robots refusal, the delta
gate, and the "store nothing rather than a placeholder" rule. Break any one of
those and the corresponding test must fail.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.core.vendor_models import (
    ExtractedFields,
    FieldMatch,
    FieldSelectors,
    ReviewReason,
    ReviewStatus,
    ScrapeStatus,
    StockStatus,
    VendorObservation,
    VendorTarget,
)
from src.extractors.vendor_listing import (
    VendorListingExtractor,
    parse_price,
    parse_stock,
    resolve_coa_url,
)
from src.infrastructure.playwright_fetcher import FetchResult, StaticPageDocument
from src.infrastructure.rate_limiter import HostRateLimiter
from src.infrastructure.robots import RobotsPolicy
from src.infrastructure.vendor_targets import load_targets, parse_target
from src.services.vendor_confidence import DeltaReviewer, score_confidence
from src.services.vendor_products_publisher import (
    VendorProductsPublisher,
    VendorProductsPublishUnavailable,
)
from src.services.vendor_scraper import VendorScrapeService


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Returns canned :class:`FetchResult`s and records what was requested."""

    def __init__(self, results):
        #: {url: FetchResult} or {url: [FetchResult, ...]} for retry sequences
        self._results = results
        self.requested = []
        self.closed = False

    def fetch(self, url):
        self.requested.append(url)
        result = self._results.get(url)
        if isinstance(result, list):
            return result.pop(0) if result else FetchResult(status=None, error="exhausted")
        if result is None:
            return FetchResult(status=404)
        return result

    def close_page(self):
        pass

    def close(self):
        self.closed = True


class FakeRepo:
    """In-memory stand-in for VendorObservationRepository."""

    def __init__(self, accepted=None):
        self._accepted = accepted or {}
        self.inserted = []

    def latest_accepted(self, vendor, url):
        return self._accepted.get((vendor, url))

    def insert(self, observation):
        self.inserted.append(observation)
        return len(self.inserted)


def allow_all_robots():
    return RobotsPolicy(
        user_agent="TestScraper/1.0",
        fetcher=lambda url: (200, "User-agent: *\nAllow: /\n"),
    )


def instant_limiter(**kwargs):
    ticks = {"t": 0.0}

    def clock():
        return ticks["t"]

    def sleeper(seconds):
        ticks["t"] += seconds

    kwargs.setdefault("default_interval", 0.0)
    return HostRateLimiter(clock=clock, sleeper=sleeper, **kwargs)


FIXED_NOW = datetime(2026, 9, 18, 3, 15, tzinfo=timezone.utc)


def make_target(**overrides):
    defaults = dict(
        slug="example-vendor",
        name="Example Vendor",
        product_urls=("https://shop.example.com/p/bpc-157",),
        selectors=FieldSelectors(
            price=("#price", ".fallback-price"),
            stock=(".stock",),
            coa=("a.coa",),
            product_name=("h1",),
        ),
        currency="USD",
    )
    defaults.update(overrides)
    return VendorTarget(**defaults)


def good_page():
    return StaticPageDocument(
        texts={
            "h1": "BPC-157 5mg",
            "#price": "$129.99",
            ".stock": "In stock",
        },
        attrs={"a.coa": {"href": "/coa/bpc-157.pdf"}},
    )


def build_service(fetcher, repo=None, robots=None, reviewer=None, limiter=None, max_retries=2):
    return VendorScrapeService(
        fetcher=fetcher,
        robots=robots or allow_all_robots(),
        rate_limiter=limiter or instant_limiter(),
        reviewer=reviewer or DeltaReviewer(min_confidence=0.6, delta_threshold=0.25),
        repository=repo,
        max_retries=max_retries,
        clock=lambda: FIXED_NOW,
    )


# ---------------------------------------------------------------------------
# Target configuration — removable without a code change
# ---------------------------------------------------------------------------


def test_targets_load_from_file(tmp_path):
    cfg = tmp_path / "targets.json"
    cfg.write_text(
        '{"targets": [{"slug": "a", "product_urls": ["https://a.test/p"],'
        ' "selectors": {"price": "#p"}}]}',
        encoding="utf-8",
    )
    targets = load_targets(cfg)
    assert [t.slug for t in targets] == ["a"]
    assert targets[0].selectors.price == ("#p",)


def test_disabled_target_is_not_returned_for_a_run(tmp_path):
    """A site must be removable without a code change — 'enabled: false' is it."""
    cfg = tmp_path / "targets.json"
    cfg.write_text(
        '{"targets": [{"slug": "a", "enabled": false, "product_urls": ["https://a.test/p"]}]}',
        encoding="utf-8",
    )
    assert load_targets(cfg) == []
    assert [t.slug for t in load_targets(cfg, include_disabled=True)] == ["a"]


def test_missing_targets_file_means_no_scraping(tmp_path):
    assert load_targets(tmp_path / "nope.json") == []


def test_one_invalid_target_does_not_drop_the_others(tmp_path):
    cfg = tmp_path / "targets.json"
    cfg.write_text(
        '[{"name": "no slug"}, {"slug": "good", "product_urls": ["https://g.test/p"]}]',
        encoding="utf-8",
    )
    assert [t.slug for t in load_targets(cfg)] == ["good"]


def test_relative_product_url_is_rejected():
    with pytest.raises(ValueError):
        parse_target({"slug": "a", "product_urls": ["/p/relative"]})


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------


def test_robots_disallowed_path_is_refused():
    robots = RobotsPolicy(
        user_agent="TestScraper/1.0",
        fetcher=lambda url: (200, "User-agent: *\nDisallow: /private/\n"),
    )
    assert robots.is_allowed("https://x.test/public/p") is True
    assert robots.is_allowed("https://x.test/private/p") is False


def test_robots_404_means_no_rules_published_so_allowed():
    robots = RobotsPolicy(user_agent="TestScraper/1.0", fetcher=lambda url: (404, ""))
    assert robots.is_allowed("https://x.test/p") is True


def test_robots_unreachable_means_disallowed():
    """We do not know the rules, so we do not crawl. Fail closed."""
    for status in (500, 503, None):
        robots = RobotsPolicy(user_agent="TestScraper/1.0", fetcher=lambda url, s=status: (s, ""))
        assert robots.is_allowed("https://x.test/p") is False, status


def test_robots_crawl_delay_is_read():
    robots = RobotsPolicy(
        user_agent="TestScraper/1.0",
        fetcher=lambda url: (200, "User-agent: *\nCrawl-delay: 12\nAllow: /\n"),
    )
    assert robots.crawl_delay("https://x.test/p") == 12.0


def test_robots_is_fetched_once_per_origin_within_ttl():
    calls = []

    def fetcher(url):
        calls.append(url)
        return 200, "User-agent: *\nAllow: /\n"

    robots = RobotsPolicy(user_agent="TestScraper/1.0", fetcher=fetcher)
    robots.is_allowed("https://x.test/a")
    robots.is_allowed("https://x.test/b")
    assert calls == ["https://x.test/robots.txt"]


def test_service_never_fetches_a_disallowed_url():
    """THE robots guard. Break it and this test must fail."""
    target = make_target()
    fetcher = FakeFetcher({target.product_urls[0]: FetchResult(200, good_page())})
    robots = RobotsPolicy(
        user_agent="TestScraper/1.0",
        fetcher=lambda url: (200, "User-agent: *\nDisallow: /p/\n"),
    )
    repo = FakeRepo()

    report = build_service(fetcher, repo=repo, robots=robots).run([target])

    assert fetcher.requested == [], "a robots-disallowed URL must never be fetched"
    assert report.observations[0].status is ScrapeStatus.ROBOTS_DISALLOWED
    assert report.observations[0].price is None


# ---------------------------------------------------------------------------
# Rate limiting and backing off
# ---------------------------------------------------------------------------


def test_rate_limiter_waits_between_requests_to_one_host():
    limiter = instant_limiter(default_interval=5.0)
    assert limiter.wait("a.test") == 0.0  # first call is free
    assert limiter.wait("a.test") == pytest.approx(5.0)


def test_rate_limiter_is_per_host():
    limiter = instant_limiter(default_interval=5.0)
    limiter.wait("a.test")
    assert limiter.wait("b.test") == 0.0


def test_crawl_delay_raises_but_never_lowers_the_floor():
    limiter = instant_limiter(default_interval=5.0)
    limiter.set_interval("a.test", 1.0)
    assert limiter.interval_for("a.test") == 5.0
    limiter.set_interval("a.test", 30.0)
    assert limiter.interval_for("a.test") == 30.0


def test_throttling_backs_off_then_abandons_the_host():
    limiter = instant_limiter(max_strikes=2, base_backoff=10.0)
    assert limiter.note_throttled("a.test") == pytest.approx(10.0)
    assert limiter.note_throttled("a.test") == pytest.approx(20.0)
    assert limiter.should_abandon("a.test") is False
    limiter.note_throttled("a.test")
    assert limiter.should_abandon("a.test") is True


def test_429_is_retried_then_recorded_as_blocked():
    url = "https://shop.example.com/p/bpc-157"
    target = make_target()
    fetcher = FakeFetcher({url: [FetchResult(429), FetchResult(429), FetchResult(429)]})
    limiter = instant_limiter(max_strikes=1, base_backoff=1.0)

    report = build_service(fetcher, limiter=limiter, max_retries=2).run([target])

    assert len(fetcher.requested) == 2, "must stop retrying once the budget is spent"
    assert report.observations[0].status is ScrapeStatus.BLOCKED


def test_403_is_recorded_and_not_worked_around():
    url = "https://shop.example.com/p/bpc-157"
    target = make_target()
    fetcher = FakeFetcher({url: FetchResult(403)})

    report = build_service(fetcher).run([target])

    assert fetcher.requested == [url], "a refusal is obeyed, not retried"
    observation = report.observations[0]
    assert observation.status is ScrapeStatus.BLOCKED
    assert "403" in (observation.failure_detail or "")
    assert observation.price is None


def test_a_blocked_host_is_not_asked_again_this_run():
    target = make_target(
        product_urls=(
            "https://shop.example.com/p/a",
            "https://shop.example.com/p/b",
        )
    )
    fetcher = FakeFetcher(
        {
            "https://shop.example.com/p/a": FetchResult(403),
            "https://shop.example.com/p/b": FetchResult(200, good_page()),
        }
    )

    report = build_service(fetcher).run([target])

    assert fetcher.requested == ["https://shop.example.com/p/a"]
    assert report.observations[1].status is ScrapeStatus.SKIPPED


# ---------------------------------------------------------------------------
# Extraction — nothing rather than a placeholder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected,currency",
    [
        ("$129.99", Decimal("129.99"), "USD"),
        ("USD 1,234.56", Decimal("1234.56"), "USD"),
        ("£89", Decimal("89"), "GBP"),
        ("€1.234,50", Decimal("1234.50"), "EUR"),
        ("From $99.00 – $189.00", Decimal("99.00"), "USD"),
        ("$250 for 10 x 5mg vials", Decimal("250"), "USD"),
    ],
)
def test_parse_price_reads_real_prices(text, expected, currency):
    price, parsed_currency = parse_price(text)
    assert price == expected
    assert parsed_currency == currency


@pytest.mark.parametrize("text", ["", None, "Call for pricing", "Price: —", "$0.00"])
def test_unreadable_price_is_none_not_zero(text):
    """House rule: absent or untrustworthy means store nothing."""
    price, _ = parse_price(text)
    assert price is None


def test_implausible_price_is_rejected():
    assert parse_price("1-800-555-0100")[0] is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("In stock", StockStatus.IN_STOCK),
        ("Add to cart", StockStatus.IN_STOCK),
        ("Out of stock", StockStatus.OUT_OF_STOCK),
        ("Sold out", StockStatus.OUT_OF_STOCK),
        ("Available on backorder", StockStatus.ON_BACKORDER),
        ("Pre-order now", StockStatus.ON_BACKORDER),
    ],
)
def test_parse_stock_maps_to_the_platform_vocabulary(text, expected):
    assert parse_stock(text) is expected


def test_unrecognised_stock_text_is_none_not_instock():
    assert parse_stock("Ships from our EU warehouse") is None
    assert parse_stock("") is None


def test_coa_url_is_absolutised_and_non_http_rejected():
    assert resolve_coa_url("/coa/x.pdf", "https://s.test/p/1") == "https://s.test/coa/x.pdf"
    assert resolve_coa_url("javascript:void(0)", "https://s.test/p/1") is None
    assert resolve_coa_url(None, "https://s.test/p/1") is None


def test_extractor_reads_price_stock_and_coa():
    fields = VendorListingExtractor().extract(
        good_page(), make_target(), "https://shop.example.com/p/bpc-157"
    )
    assert fields.product_name == "BPC-157 5mg"
    assert fields.price == Decimal("129.99")
    assert fields.currency == "USD"
    assert fields.stock_status is StockStatus.IN_STOCK
    assert fields.coa_url == "https://shop.example.com/coa/bpc-157.pdf"
    assert fields.matches["price"].selector_index == 0


def test_a_price_selector_that_matches_junk_records_no_match():
    document = StaticPageDocument(texts={"#price": "Call for pricing", "h1": "BPC-157"})
    fields = VendorListingExtractor().extract(document, make_target(), "https://s.test/p")
    assert fields.price is None
    assert "price" not in fields.matches


def test_configured_currency_is_only_a_fallback():
    document = StaticPageDocument(texts={"#price": "129.99"})
    fields = VendorListingExtractor().extract(
        document, make_target(currency="EUR"), "https://s.test/p"
    )
    assert fields.currency == "EUR"

    document = StaticPageDocument(texts={"#price": "$129.99"})
    fields = VendorListingExtractor().extract(
        document, make_target(currency="EUR"), "https://s.test/p"
    )
    assert fields.currency == "USD", "the page's own currency wins over our guess"


# ---------------------------------------------------------------------------
# Confidence — scored on what matched, not on the run completing
# ---------------------------------------------------------------------------


def _fields(**matches):
    extracted = ExtractedFields()
    for name, index in matches.items():
        extracted.matches[name] = FieldMatch(index, f"sel-{name}")
    return extracted


def test_full_match_scores_one():
    breakdown = score_confidence(
        _fields(price=0, stock=0, coa=0, product_name=0), make_target()
    )
    assert breakdown.score == pytest.approx(1.0)


def test_a_missing_price_dominates_the_score():
    breakdown = score_confidence(_fields(stock=0, coa=0, product_name=0), make_target())
    assert breakdown.score == pytest.approx(0.45)
    assert breakdown.contributions["price"] == 0.0


def test_a_fallback_selector_is_discounted():
    primary = score_confidence(_fields(price=0, stock=0, coa=0, product_name=0), make_target())
    fallback = score_confidence(_fields(price=1, stock=0, coa=0, product_name=0), make_target())
    assert fallback.score < primary.score
    assert any("fallback" in note for note in fallback.notes)


def test_fields_the_target_never_asked_for_are_not_penalised():
    target = make_target(selectors=FieldSelectors(price=("#price",)))
    breakdown = score_confidence(_fields(price=0), target)
    assert breakdown.score == pytest.approx(1.0)
    assert "coa" not in breakdown.contributions


def test_confidence_is_zero_when_nothing_matched():
    assert score_confidence(ExtractedFields(), make_target()).score == 0.0


def test_a_completed_run_with_no_matches_still_scores_zero():
    """Completion is not evidence. Only matches are."""
    url = "https://shop.example.com/p/bpc-157"
    fetcher = FakeFetcher({url: FetchResult(200, StaticPageDocument(texts={"h2": "hello"}))})
    report = build_service(fetcher).run([make_target()])
    observation = report.observations[0]
    assert observation.status is ScrapeStatus.OK  # the run was fine
    assert observation.confidence == 0.0  # the extraction was not
    assert observation.review_status is ReviewStatus.FLAGGED


# ---------------------------------------------------------------------------
# Delta review — a large move flags, it does not overwrite
# ---------------------------------------------------------------------------


def _observation(price, confidence=1.0, currency="USD", when=FIXED_NOW):
    return VendorObservation(
        vendor="example-vendor",
        url="https://shop.example.com/p/bpc-157",
        observed_at=when,
        price=Decimal(price) if price is not None else None,
        currency=currency,
        confidence=confidence,
        review_status=ReviewStatus.ACCEPTED,
    )


def test_first_good_reading_is_accepted():
    decision = DeltaReviewer().assess(_observation("100.00"), None)
    assert decision.status is ReviewStatus.ACCEPTED


def test_small_move_is_accepted():
    decision = DeltaReviewer(delta_threshold=0.25).assess(
        _observation("110.00"), _observation("100.00")
    )
    assert decision.status is ReviewStatus.ACCEPTED


def test_large_move_is_flagged_not_applied():
    """THE delta guard. Break it and this test must fail."""
    decision = DeltaReviewer(delta_threshold=0.25).assess(
        _observation("40.00"), _observation("100.00")
    )
    assert decision.status is ReviewStatus.FLAGGED
    assert decision.reason is ReviewReason.PRICE_DELTA
    assert decision.supersedes_previous is False
    assert "previous accepted value retained" in decision.note


def test_large_upward_move_is_flagged_too():
    decision = DeltaReviewer(delta_threshold=0.25).assess(
        _observation("500.00"), _observation("100.00")
    )
    assert decision.reason is ReviewReason.PRICE_DELTA


def test_delta_is_measured_exactly_at_the_threshold():
    reviewer = DeltaReviewer(delta_threshold=0.25)
    assert reviewer.assess(_observation("125.00"), _observation("100.00")).status is (
        ReviewStatus.ACCEPTED
    )
    assert reviewer.assess(_observation("125.01"), _observation("100.00")).status is (
        ReviewStatus.FLAGGED
    )


def test_no_price_is_flagged_and_never_a_placeholder():
    decision = DeltaReviewer().assess(_observation(None), _observation("100.00"))
    assert decision.status is ReviewStatus.FLAGGED
    assert decision.reason is ReviewReason.NO_PRICE
    assert decision.supersedes_previous is False


def test_low_confidence_is_flagged_even_when_the_price_barely_moved():
    decision = DeltaReviewer(min_confidence=0.6).assess(
        _observation("101.00", confidence=0.3), _observation("100.00")
    )
    assert decision.reason is ReviewReason.LOW_CONFIDENCE


def test_currency_change_is_flagged_rather_than_compared():
    decision = DeltaReviewer().assess(
        _observation("100.00", currency="EUR"), _observation("100.00", currency="USD")
    )
    assert decision.reason is ReviewReason.CURRENCY_CHANGED


def test_service_flags_a_large_delta_against_the_last_accepted_price():
    url = "https://shop.example.com/p/bpc-157"
    target = make_target()
    document = StaticPageDocument(
        texts={"h1": "BPC-157 5mg", "#price": "$19.99", ".stock": "In stock"},
        attrs={"a.coa": {"href": "/coa/x.pdf"}},
    )
    previous = _observation(
        "129.99", when=FIXED_NOW - timedelta(days=1)
    )
    repo = FakeRepo(accepted={("example-vendor", url): previous})
    fetcher = FakeFetcher({url: FetchResult(200, document)})

    report = build_service(fetcher, repo=repo).run([target])

    observation = report.observations[0]
    assert observation.confidence == pytest.approx(1.0), "the extraction itself was clean"
    assert observation.review_status is ReviewStatus.FLAGGED
    assert observation.review_reason is ReviewReason.PRICE_DELTA
    # The previously accepted reading is untouched — the flagged one is stored
    # alongside it, not over it.
    assert repo.latest_accepted("example-vendor", url) is previous


def test_a_clean_reading_is_accepted_and_stored():
    url = "https://shop.example.com/p/bpc-157"
    repo = FakeRepo()
    fetcher = FakeFetcher({url: FetchResult(200, good_page())})

    report = build_service(fetcher, repo=repo).run([make_target()])

    observation = report.observations[0]
    assert observation.review_status is ReviewStatus.ACCEPTED
    assert observation.price == Decimal("129.99")
    assert observation.stock_status is StockStatus.IN_STOCK
    assert observation.coa_url.endswith("/coa/bpc-157.pdf")
    assert len(repo.inserted) == 1
    assert fetcher.closed is True


def test_report_counts_summarise_the_run():
    target = make_target(
        product_urls=("https://shop.example.com/p/a", "https://other.example.com/p/b")
    )
    fetcher = FakeFetcher(
        {
            "https://shop.example.com/p/a": FetchResult(200, good_page()),
            "https://other.example.com/p/b": FetchResult(500),
        }
    )
    report = build_service(fetcher, max_retries=0, limiter=instant_limiter(max_strikes=0)).run(
        [target]
    )
    payload = report.to_dict()
    assert payload["urls_processed"] == 2
    assert payload["status_counts"]["ok"] == 1
    assert payload["review_counts"]["accepted"] == 1


def test_observation_serialises_money_as_a_string_and_gaps_as_null():
    payload = _observation("129.99").to_dict()
    assert payload["price"] == "129.99"
    assert payload["stock_status"] is None
    assert payload["coa_url"] is None


# ---------------------------------------------------------------------------
# The vendor_products seam
# ---------------------------------------------------------------------------


def test_publisher_is_a_no_op_while_disabled():
    result = VendorProductsPublisher(enabled=False).publish([_observation("100.00")])
    assert result.published == 0
    assert "disabled" in result.reason


def test_publisher_refuses_loudly_rather_than_pretending_to_publish():
    """Turning the flag on must not look like success — the table cannot take
    a scraped row yet (no `source` column, non-null `wc_product_id`, and no
    connection to the platform database)."""
    with pytest.raises(VendorProductsPublishUnavailable) as exc:
        VendorProductsPublisher(enabled=True).publish([_observation("100.00")])
    assert "source" in str(exc.value)


def test_publisher_never_offers_a_flagged_observation():
    flagged = _observation("100.00")
    flagged.review_status = ReviewStatus.FLAGGED
    with pytest.raises(VendorProductsPublishUnavailable):
        VendorProductsPublisher(enabled=True).publish([_observation("100.00")])
    # With only flagged input there is nothing publishable, but the seam still
    # refuses rather than reporting a successful publish of zero rows.
    with pytest.raises(VendorProductsPublishUnavailable):
        VendorProductsPublisher(enabled=True).publish([flagged])
