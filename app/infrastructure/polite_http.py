"""Polite plain-HTTP client for selector-free competitor discovery (AAD-1).

The Playwright fetcher reads one rendered product page at a time. URL-only
discovery mostly needs JSON (WooCommerce Store API, Shopify products.json),
XML sitemaps and static HTML, which a browser would only slow down. This
client fetches those with the same rules the browser path follows:

* **robots.txt first.** Every URL — the Store API endpoint, a sitemap, a
  product page and each redirect hop — is checked against the site's rules for
  our user-agent before it is requested. A disallowed path is never fetched.
* **SSRF guard on every hop** (:func:`~app.infrastructure.url_safety.check_url`,
  fresh DNS lookup), redirects followed by hand.
* **Paced per host** through the shared :class:`HostRateLimiter` (our floor, the
  target's interval, robots.txt ``Crawl-delay``), and at most
  ``concurrency`` (1..4) requests in flight.
* **A hard request budget** per discovery, a timeout per request and a cap on
  the response size.
* **No retry storm.** A request is made once. 403/401/451 ends the host for
  the run; 429/5xx backs off through the limiter's strike budget and the
  caller moves on — nothing is re-requested here.
* An honest User-Agent (the same string robots.txt was evaluated for).

The single-hop transport is injected, so tests replay recorded responses with
no network at all.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

from app.infrastructure.rate_limiter import HostRateLimiter
from app.infrastructure.robots import RobotsPolicy
from app.infrastructure.url_safety import UnsafeTargetURLError, check_url

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
#: A product catalogue page or sitemap is well under this; anything larger is
#: not something we asked for.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_REDIRECT_STATUSES = (301, 302, 303, 307, 308)
_CHARSET_RE = re.compile(r"charset=([\w.-]+)", re.IGNORECASE)

ACCEPT_JSON = "application/json"
ACCEPT_HTML = "text/html,application/xhtml+xml"
ACCEPT_XML = "application/xml,text/xml"


@dataclass
class HttpResult:
    """One GET, after redirects. ``status`` is ``None`` when nothing came back."""

    url: str
    status: int | None
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    #: True when robots.txt disallowed the URL (or a redirect hop) — not fetched.
    robots_disallowed: bool = False
    #: True when the discovery's request budget was spent — not fetched.
    budget_exhausted: bool = False

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300

    @property
    def refused(self) -> bool:
        return self.status in (401, 403, 451)

    @property
    def throttled(self) -> bool:
        return self.status is not None and (self.status == 429 or self.status >= 500)

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    def json(self) -> Any:
        """Parsed JSON body, or ``None`` when the body is not JSON."""
        if not self.ok or not self.text:
            return None
        try:
            return json.loads(self.text)
        except (TypeError, ValueError):
            return None


#: ``(url, headers, timeout_seconds) -> HttpResult`` for ONE hop, no redirects.
Transport = Callable[[str, dict[str, str], float], HttpResult]


def _decode(body: bytes, content_type: str) -> str:
    match = _CHARSET_RE.search(content_type or "")
    encoding = match.group(1) if match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def requests_transport(url: str, headers: dict[str, str], timeout: float) -> HttpResult:
    """The real single-hop GET (``requests``, redirects off, size-capped)."""
    import requests  # lazy, like the robots fetcher

    try:
        with requests.get(
            url, headers=headers, timeout=timeout, allow_redirects=False, stream=True
        ) as resp:
            resp_headers = {k.lower(): v for k, v in (resp.headers or {}).items()}
            chunks = []
            size = 0
            for chunk in resp.iter_content(65536):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    return HttpResult(
                        url=url, status=None, headers=resp_headers,
                        error=f"response larger than {MAX_RESPONSE_BYTES} bytes",
                    )
                chunks.append(chunk)
            text = _decode(b"".join(chunks), resp_headers.get("content-type", ""))
            return HttpResult(url=url, status=resp.status_code, text=text, headers=resp_headers)
    except Exception as exc:  # noqa: BLE001 — any transport failure is "no response"
        return HttpResult(url=url, status=None, error=f"{type(exc).__name__}: {exc}")


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class PoliteHttpClient:
    """GETs under robots.txt, the SSRF guard, the host rate limit and a budget.

    One client serves one discovery (one target's store); ``max_requests``
    caps every request it makes, redirect hops included.
    """

    def __init__(
        self,
        robots: RobotsPolicy,
        limiter: HostRateLimiter,
        *,
        user_agent: str | None = None,
        transport: Transport | None = None,
        timeout_seconds: float = 15.0,
        max_requests: int = 60,
        min_interval_seconds: float = 0.0,
        concurrency: int = 2,
    ):
        self._robots = robots
        self._limiter = limiter
        self._user_agent = user_agent or robots.user_agent
        self._transport = transport or requests_transport
        self._timeout = max(1.0, float(timeout_seconds))
        self._max_requests = max(1, int(max_requests))
        self._min_interval = max(0.0, float(min_interval_seconds))
        #: Bounded concurrency: never more than 4 in flight against a host.
        self.concurrency = max(1, min(4, int(concurrency)))
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(self.concurrency)
        self.requests_made = 0

    # -- gates -------------------------------------------------------------

    @property
    def budget_left(self) -> int:
        return max(0, self._max_requests - self.requests_made)

    def is_allowed(self, url: str) -> bool:
        return self._robots.is_allowed(url)

    def robots_sitemaps(self, url: str) -> list[str]:
        """``Sitemap:`` lines from the site's robots.txt (already cached)."""
        return self._robots.sitemaps(url)

    def acquire(self, url: str) -> HttpResult | None:
        """Run every gate for one request to ``url`` and count it.

        Returns ``None`` when the request may go ahead (after waiting out the
        host's interval), else the :class:`HttpResult` explaining why not.
        Also used before a rendered browser fetch, so that path spends the
        same budget and obeys the same rules.
        """
        host = urlsplit(url).netloc.lower()
        if self._limiter.should_abandon(host):
            return HttpResult(url=url, status=None, error=self._limiter.abandon_reason(host) or "host abandoned")
        if not self._robots.is_allowed(url):
            return HttpResult(
                url=url, status=None, robots_disallowed=True,
                error="robots.txt disallows this path for our user-agent",
            )
        try:
            check_url(url)
        except UnsafeTargetURLError as exc:
            return HttpResult(url=url, status=None, error=f"blocked (non-public address): {exc}")
        with self._lock:
            if self.requests_made >= self._max_requests:
                return HttpResult(
                    url=url, status=None, budget_exhausted=True,
                    error=f"request budget of {self._max_requests} spent",
                )
            self.requests_made += 1
            self._limiter.set_interval(host, self._min_interval)
            delay = self._robots.crawl_delay(url)
            if delay:
                self._limiter.set_interval(host, delay)
            # Spaced request *starts*; the semaphore bounds what is in flight.
            self._limiter.wait(host)
        return None

    # -- GET ---------------------------------------------------------------

    def get(self, url: str, accept: str = ACCEPT_HTML) -> HttpResult:
        headers = {
            "User-Agent": self._user_agent,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        }
        current = url
        with self._slots:
            for _hop in range(MAX_REDIRECTS + 1):
                refusal = self.acquire(current)
                if refusal is not None:
                    return refusal
                result = self._transport(current, headers, self._timeout)
                location = result.header("location") if result.status in _REDIRECT_STATUSES else None
                if location:
                    current = urljoin(current, location)
                    continue
                self._note(current, result)
                result.url = current
                return result
        return HttpResult(url=url, status=None, error=f"more than {MAX_REDIRECTS} redirects")

    def _note(self, url: str, result: HttpResult) -> None:
        host = urlsplit(url).netloc.lower()
        with self._lock:
            if result.refused:
                self._limiter.note_blocked(host, f"HTTP {result.status}")
            elif result.throttled:
                # Backs off (sleeps) and counts a strike; past the budget the
                # host is abandoned for the run. The request is NOT retried.
                self._limiter.note_throttled(host, _retry_after(result.header("retry-after")))
            elif result.ok:
                self._limiter.note_success(host)


__all__ = [
    "ACCEPT_HTML",
    "ACCEPT_JSON",
    "ACCEPT_XML",
    "HttpResult",
    "PoliteHttpClient",
    "Transport",
    "requests_transport",
]
