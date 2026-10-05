"""SSRF guard for admin-managed competitor targets.

A target URL is fetched from inside our network, so it must never be allowed
to point at loopback, private ranges, link-local (the 169.254.169.254 cloud
metadata endpoint), multicast/reserved space, or a hostname resolving there —
checked when the target is saved *and* again on every fetch and redirect hop
(DNS rebinding). Offline: DNS is stubbed, the browser is faked, except for
the last test, which uses a real Chromium when one is available.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.infrastructure.url_safety as url_safety
from src.config import settings
from src.infrastructure.playwright_fetcher import PlaywrightPageFetcher
from src.infrastructure.robots import default_robots_fetcher
from src.infrastructure.url_safety import UnsafeTargetURLError, check_url, is_public_address
from src.infrastructure.vendor_targets import VendorTargetConfigError, parse_target
from src.tests.test_vendor_targets_api import (  # noqa: F401 — `api` is a fixture
    _playwright_fetcher_or_skip,
    api,
    fixture_site,
    payload,
    run,
)

PUBLIC_IP = "93.184.216.34"
_REAL_RESOLVER = url_safety._system_resolver

BLOCKED_URLS = [
    "http://127.0.0.1:8005/health",
    "http://127.1/",
    "http://localhost/",
    "http://api.localhost/",
    "http://[::1]/",
    "http://0.0.0.0/",
    "http://10.0.0.5/",
    "http://172.16.3.4/",
    "http://192.168.1.10/",
    "http://169.254.169.254/latest/meta-data/",
    "http://100.64.0.1/",           # shared / CGNAT
    "http://224.0.0.251/",          # multicast
    "http://240.0.0.1/",            # reserved
    "http://[fe80::1]/",
    "http://[fd00::1]/",
    "http://[::ffff:127.0.0.1]/",   # IPv4-mapped loopback
    "http://[::ffff:169.254.169.254]/",
    "http://2130706433/",           # 127.0.0.1 as a decimal integer
]


@pytest.fixture
def dns(monkeypatch):
    """A controllable resolver: ``dns["host"] = ["1.2.3.4"]``."""
    table = {}

    def resolve(host):
        if host in table:
            return list(table[host])
        # Numeric forms (2130706433, 127.1) are resolved locally by the OS,
        # never over the network — let the real resolver handle those.
        if host.replace(".", "").isdigit():
            return _REAL_RESOLVER(host)
        raise OSError(f"no such host {host}")

    monkeypatch.setattr(url_safety, "_system_resolver", resolve)
    return table


# ── the address rule ────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_internal_addresses_are_refused(url, dns):
    with pytest.raises(UnsafeTargetURLError):
        check_url(url)


def test_a_public_address_is_allowed(dns):
    check_url(f"https://{PUBLIC_IP}/p/1")
    dns["shop.example"] = [PUBLIC_IP]
    check_url("https://shop.example/p/1")


def test_hostname_resolving_to_an_internal_address_is_refused(dns):
    dns["metadata.attacker.example"] = ["169.254.169.254"]
    with pytest.raises(UnsafeTargetURLError, match="non-public"):
        check_url("https://metadata.attacker.example/latest")


def test_one_internal_address_among_public_ones_is_enough_to_refuse(dns):
    dns["mixed.example"] = [PUBLIC_IP, "10.1.2.3"]
    with pytest.raises(UnsafeTargetURLError):
        check_url("https://mixed.example/")


def test_unresolvable_host_is_refused(dns):
    with pytest.raises(UnsafeTargetURLError, match="does not resolve"):
        check_url("https://nowhere.example/")


def test_is_public_address():
    assert is_public_address(PUBLIC_IP)
    assert not is_public_address("169.254.169.254")
    assert not is_public_address("not-an-ip")


# ── save time ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        {"slug": "x", "product_urls": ["http://127.0.0.1:8005/api/v1/health"]},
        {"slug": "x", "product_urls": ["http://169.254.169.254/latest/meta-data/"]},
        {"slug": "x", "listing_url": "http://10.0.0.5/shop", "listing_link_selector": "a"},
        {"slug": "x", "listing_url": "http://localhost:8080/", "listing_link_selector": "a"},
    ],
)
def test_parse_target_refuses_internal_literals(raw):
    with pytest.raises(VendorTargetConfigError, match="not allowed"):
        parse_target(raw)


def test_api_refuses_a_loopback_target_with_422(api):
    vendors, repo, _ = api
    with pytest.raises(HTTPException) as exc:
        run(vendors.create_vendor_target(payload(vendors, product_urls=["http://127.0.0.1:8005/"])))
    assert exc.value.status_code == 422
    assert repo.targets == {}


def test_api_refuses_a_metadata_listing_url_on_update(api):
    vendors, repo, _ = api
    run(vendors.create_vendor_target(payload(vendors)))
    with pytest.raises(HTTPException) as exc:
        run(vendors.update_vendor_target("rival", payload(
            vendors, listing_url="http://169.254.169.254/", listing_link_selector="a")))
    assert exc.value.status_code == 422
    assert repo.targets["rival"].listing_url is None


def test_api_refuses_a_hostname_that_resolves_internally(api, monkeypatch):
    vendors, repo, _ = api
    monkeypatch.setattr(url_safety, "_system_resolver",
                        lambda host: ["10.0.0.7"] if host == "intranet.example" else [PUBLIC_IP])
    with pytest.raises(HTTPException) as exc:
        run(vendors.create_vendor_target(payload(vendors, product_urls=["https://intranet.example/p"])))
    assert exc.value.status_code == 422
    assert "non-public" in exc.value.detail
    assert repo.targets == {}


# ── the local-testing escape hatch ──────────────────────────────────────────


def test_private_targets_are_refused_by_default():
    assert settings.VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS is False


def test_allow_private_setting_permits_local_fixture_targets(monkeypatch):
    monkeypatch.setattr(settings, "VENDOR_SCRAPE_ALLOW_PRIVATE_TARGETS", True)
    target = parse_target({"slug": "fixture", "product_urls": ["http://127.0.0.1:5555/p.html"]})
    assert target.product_urls == ("http://127.0.0.1:5555/p.html",)
    check_url("http://127.0.0.1:5555/p.html")
    with pytest.raises(UnsafeTargetURLError):  # the scheme rule still holds
        check_url("file:///etc/passwd")


# ── fetch time: the page fetcher ────────────────────────────────────────────


def _fetcher_without_browser(monkeypatch):
    fetcher = PlaywrightPageFetcher(user_agent="test-agent")

    def no_browser():
        raise AssertionError("the browser must not be started for a refused URL")

    monkeypatch.setattr(fetcher, "_ensure_started", no_browser)
    return fetcher


def test_fetcher_refuses_an_internal_url_before_starting_a_browser(monkeypatch, dns):
    fetcher = _fetcher_without_browser(monkeypatch)
    result = fetcher.fetch("http://169.254.169.254/latest/meta-data/")
    assert result.status is None and not result.ok
    assert "blocked" in (result.error or "")


def test_fetch_time_recheck_catches_dns_rebinding(monkeypatch, dns):
    dns["rival.example"] = [PUBLIC_IP]
    target = parse_target({"slug": "rival", "product_urls": ["https://rival.example/p/1"]})
    from src.infrastructure.vendor_targets import check_target_addresses

    check_target_addresses(target)  # public when it was saved

    dns["rival.example"] = ["127.0.0.1"]  # ...and loopback by the time it is fetched
    result = _fetcher_without_browser(monkeypatch).fetch(target.product_urls[0])
    assert "blocked" in (result.error or "")


class _FakeResponse:
    def __init__(self, status, location=None, body="ok"):
        self.status = status
        self.headers = {"location": location} if location else {}
        self.body = body


class _FakeRoute:
    def __init__(self, url, first_response, resource_type="document"):
        self.request = SimpleNamespace(url=url, resource_type=resource_type)
        self._first = first_response
        self.fulfilled = None
        self.aborted = None
        self.continued = False

    def fetch(self, max_redirects=None):
        assert max_redirects == 0, "the browser must never follow a redirect itself"
        return self._first

    def fulfill(self, response):
        self.fulfilled = response

    def abort(self, error_code=None):
        self.aborted = error_code

    def continue_(self):
        self.continued = True


def _fetcher_with_context(later_hops):
    fetcher = PlaywrightPageFetcher(user_agent="test-agent")
    sent = []

    def fetch(url, method=None, max_redirects=None):
        assert max_redirects == 0
        sent.append(url)
        return later_hops[url]

    fetcher._context = SimpleNamespace(request=SimpleNamespace(fetch=fetch))
    return fetcher, sent


def test_redirect_to_the_metadata_endpoint_is_aborted_before_it_is_sent(dns):
    dns["rival.example"] = [PUBLIC_IP]
    fetcher, sent = _fetcher_with_context({})
    route = _FakeRoute("https://rival.example/p/1",
                       _FakeResponse(302, location="http://169.254.169.254/latest/meta-data/"))

    fetcher._guard_route(route)

    assert route.aborted == "blockedbyclient" and route.fulfilled is None
    assert sent == []  # the internal hop was never requested
    assert "not a public address" in fetcher._blocked_reason


def test_redirect_to_a_host_that_resolves_internally_is_aborted(dns):
    dns["rival.example"] = [PUBLIC_IP]
    dns["cdn.rival.example"] = ["192.168.0.10"]
    fetcher, sent = _fetcher_with_context({})
    route = _FakeRoute("https://rival.example/p/1", _FakeResponse(301, location="https://cdn.rival.example/p/1"))
    fetcher._guard_route(route)
    assert route.aborted == "blockedbyclient" and sent == []


def test_public_redirects_are_followed_hop_by_hop_and_fulfilled(dns):
    dns["rival.example"] = [PUBLIC_IP]
    dns["www.rival.example"] = [PUBLIC_IP]
    final = _FakeResponse(200, body="<html>price</html>")
    fetcher, sent = _fetcher_with_context({"https://www.rival.example/p/1": final})
    route = _FakeRoute("http://rival.example/p/1", _FakeResponse(301, location="https://www.rival.example/p/1"))

    fetcher._guard_route(route)

    assert sent == ["https://www.rival.example/p/1"]
    assert route.fulfilled is final and route.aborted is None


def test_subrequest_to_an_internal_address_is_aborted(dns):
    fetcher, _ = _fetcher_with_context({})
    route = _FakeRoute("http://10.0.0.5/internal.js", _FakeResponse(200))
    fetcher._guard_route(route)
    assert route.aborted == "blockedbyclient" and route.fulfilled is None


# FEEDBACK-3 G11: every image, font and stylesheet went through the guard one
# at a time and the product page missed its navigation timeout.
@pytest.mark.parametrize("resource_type", ["image", "media", "font", "stylesheet"])
def test_assets_a_scrape_never_reads_are_dropped_without_a_request(dns, resource_type):
    dns["rival.example"] = [PUBLIC_IP]
    fetcher, sent = _fetcher_with_context({})
    route = _FakeRoute("https://rival.example/logo.png", _FakeResponse(200), resource_type=resource_type)

    fetcher._guard_route(route)

    assert route.aborted == "blockedbyclient" and route.fulfilled is None and sent == []


@pytest.mark.parametrize("resource_type", ["script", "xhr", "fetch"])
def test_scripts_are_dropped_on_the_static_pass(dns, resource_type):
    dns["rival.example"] = [PUBLIC_IP]
    fetcher, sent = _fetcher_with_context({})
    route = _FakeRoute("https://rival.example/app.js", _FakeResponse(200), resource_type=resource_type)

    fetcher._guard_route(route)

    assert route.aborted == "blockedbyclient" and sent == []


@pytest.mark.parametrize(
    "resource_type, rendered",
    [("document", False), ("document", True), ("script", True), ("xhr", True), ("fetch", True)],
)
def test_documents_and_rendered_scripts_still_go_through_the_guard(dns, resource_type, rendered):
    dns["rival.example"] = [PUBLIC_IP]
    fetcher, _ = _fetcher_with_context({})
    fetcher._render_scripts = rendered
    final = _FakeResponse(200, body="<html>price</html>")
    route = _FakeRoute("https://rival.example/p/1", final, resource_type=resource_type)

    fetcher._guard_route(route)

    assert route.fulfilled is final and route.aborted is None


def test_non_network_schemes_are_left_to_the_browser(dns):
    fetcher, _ = _fetcher_with_context({})
    route = _FakeRoute("data:text/plain,hi", _FakeResponse(200))
    fetcher._guard_route(route)
    assert route.continued and route.aborted is None


# ── fetch time: robots.txt ──────────────────────────────────────────────────


class _Resp:
    def __init__(self, status_code, text="", location=None):
        self.status_code = status_code
        self.text = text
        self.headers = {"Location": location} if location else {}


def _record_requests(monkeypatch, responses):
    import requests

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return responses[url]

    monkeypatch.setattr(requests, "get", get)
    return calls


def test_robots_fetch_to_an_internal_address_is_never_sent(monkeypatch, dns):
    calls = _record_requests(monkeypatch, {})
    assert default_robots_fetcher("http://127.0.0.1:8005/robots.txt") == (None, "")
    assert calls == []


def test_robots_redirect_into_an_internal_address_is_not_followed(monkeypatch, dns):
    dns["rival.example"] = [PUBLIC_IP]
    calls = _record_requests(monkeypatch, {
        "https://rival.example/robots.txt": _Resp(302, location="http://169.254.169.254/latest/meta-data/"),
    })
    assert default_robots_fetcher("https://rival.example/robots.txt") == (None, "")
    assert [url for url, _ in calls] == ["https://rival.example/robots.txt"]
    assert calls[0][1]["allow_redirects"] is False


def test_robots_public_redirect_is_followed(monkeypatch, dns):
    dns["rival.example"] = [PUBLIC_IP]
    dns["www.rival.example"] = [PUBLIC_IP]
    _record_requests(monkeypatch, {
        "https://rival.example/robots.txt": _Resp(301, location="https://www.rival.example/robots.txt"),
        "https://www.rival.example/robots.txt": _Resp(200, text="User-agent: *\nDisallow: /private/"),
    })
    status, body = default_robots_fetcher("https://rival.example/robots.txt")
    assert status == 200 and "Disallow" in body


# ── real browser, real local server ─────────────────────────────────────────


def test_real_browser_never_reaches_a_loopback_site_by_default(fixture_site):
    base, requested = fixture_site
    fetcher = _playwright_fetcher_or_skip()
    try:
        result = fetcher.fetch(f"{base}/index.html")
    finally:
        fetcher.close()
    assert not result.ok and "blocked" in (result.error or "")
    assert requested == []


def test_real_browser_redirect_into_a_refused_host_is_never_sent(monkeypatch):
    """Two local servers: A answers 302 -> B. Only B is "internal" (the guard is
    told so by port), so this proves, in a real Chromium, that a redirect hop
    is checked before it is sent — B must never see a request."""
    import http.server
    import threading

    import src.infrastructure.playwright_fetcher as pf

    hits = {"a": [], "b": []}

    def server(name, handler_body):
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                hits[name].append(self.path)
                handler_body(self)

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv

    def internal(h):
        h.send_response(200)
        h.send_header("Content-Type", "text/html")
        h.end_headers()
        h.wfile.write(b"<html><body class='price'>$1.00</body></html>")

    srv_b = server("b", internal)
    b_url = f"http://127.0.0.1:{srv_b.server_address[1]}/latest/meta-data/"

    def redirecting(h):
        h.send_response(302)
        h.send_header("Location", b_url)
        h.end_headers()

    srv_a = server("a", redirecting)
    a_url = f"http://127.0.0.1:{srv_a.server_address[1]}/p/1"

    b_port = f":{srv_b.server_address[1]}"

    def guard(url, **kwargs):
        if b_port in url:
            raise UnsafeTargetURLError("host '127.0.0.1' is not a public address")

    monkeypatch.setattr(pf, "check_url", guard)
    fetcher = _playwright_fetcher_or_skip()
    try:
        result = fetcher.fetch(a_url)
    finally:
        fetcher.close()
        srv_a.shutdown()
        srv_b.shutdown()
        srv_a.server_close()
        srv_b.server_close()

    assert hits["a"] == ["/p/1"]
    assert hits["b"] == []
    assert not result.ok and "blocked" in (result.error or "")
