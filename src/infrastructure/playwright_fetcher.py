"""Playwright page fetcher for competitor vendor pages (#288).

Vendor product pages price themselves in JavaScript often enough that a plain
HTTP GET is not sufficient, so this is a real (headless) browser.

**This fetcher is deliberately not stealthy.** Contrast it with
``src/infrastructure/webdriver_factory.py``, which spoofs a Chrome
User-Agent and patches ``navigator.webdriver`` — that exists for *our own*
pep-pedia source. Here we are reading other companies' sites, so:

* the User-Agent names this scraper and carries a contact URL;
* ``navigator.webdriver`` is left exactly as Playwright sets it;
* no automation fingerprints are masked, no proxies are rotated, no CAPTCHA
  is answered. A 403 is a refusal we record and obey.

Playwright is imported lazily inside :meth:`PlaywrightPageFetcher.fetch`, so
this module — and everything that imports it — stays importable (and
unit-testable) in an environment where the browser binaries were never
installed. Tests inject a fake fetcher and never reach this code path.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The seam every extractor is written against
# ---------------------------------------------------------------------------


class PageDocument(Protocol):
    """The narrow slice of a rendered page the extractor needs.

    Keeping it this small is what lets the whole extraction/confidence layer
    be tested with a dictionary instead of a browser.
    """

    def query_text(self, selector: str) -> Optional[str]:
        """Visible text of the first match, or ``None``."""

    def query_attr(self, selector: str, attr: str) -> Optional[str]:
        """Attribute of the first match, or ``None``."""


@dataclass
class FetchResult:
    """Outcome of loading one URL."""

    #: HTTP status of the main document. ``None`` when navigation never
    #: produced a response (DNS failure, timeout, browser crash).
    status: Optional[int]
    document: Optional[PageDocument] = None
    error: Optional[str] = None
    #: ``Retry-After`` in seconds if the site sent one we could parse.
    retry_after: Optional[float] = None

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300 and self.document is not None

    @property
    def throttled(self) -> bool:
        """429 or 5xx — back off and try again, within budget."""
        return self.status is not None and (self.status == 429 or self.status >= 500)

    @property
    def refused(self) -> bool:
        """403/401/451 — a deliberate refusal. Record it and stop."""
        return self.status in (401, 403, 451)


class PageFetcher(Protocol):
    def fetch(self, url: str) -> FetchResult: ...

    def close_page(self) -> None:
        """Release the page the last :meth:`fetch` returned a document for."""

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Playwright implementation
# ---------------------------------------------------------------------------


class _PlaywrightPageDocument:
    """Adapts a Playwright ``Page`` to :class:`PageDocument`."""

    def __init__(self, page: Any):
        self._page = page

    def query_text(self, selector: str) -> Optional[str]:
        try:
            element = self._page.query_selector(selector)
        except Exception as exc:  # noqa: BLE001 — a bad selector is a config bug, not a crash
            logger.debug("Selector %r failed: %s", selector, exc)
            return None
        if element is None:
            return None
        try:
            text = element.inner_text()
        except Exception:  # noqa: BLE001
            return None
        text = (text or "").strip()
        return text or None

    def query_attr(self, selector: str, attr: str) -> Optional[str]:
        try:
            element = self._page.query_selector(selector)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Selector %r failed: %s", selector, exc)
            return None
        if element is None:
            return None
        try:
            value = element.get_attribute(attr)
        except Exception:  # noqa: BLE001
            return None
        value = (value or "").strip()
        return value or None


@dataclass
class StaticPageDocument:
    """A :class:`PageDocument` backed by two plain dicts.

    Used by tests, and by anything that has already captured a page's fields
    (a fixture, a replayed extraction) and wants to re-run scoring over it
    without a browser.
    """

    texts: Dict[str, str] = field(default_factory=dict)
    attrs: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def query_text(self, selector: str) -> Optional[str]:
        value = self.texts.get(selector)
        return value.strip() if isinstance(value, str) and value.strip() else None

    def query_attr(self, selector: str, attr: str) -> Optional[str]:
        value = (self.attrs.get(selector) or {}).get(attr)
        return value.strip() if isinstance(value, str) and value.strip() else None


class PlaywrightPageFetcher:
    """Headless Chromium, one browser per run, one page per URL.

    Args:
        user_agent: sent verbatim. Must be the same string the
            :class:`~src.infrastructure.robots.RobotsPolicy` evaluated, or we
            would be obeying rules written for somebody else.
        timeout_ms: navigation timeout.
    """

    def __init__(self, user_agent: str, timeout_ms: int = 20000):
        self._user_agent = user_agent
        self._timeout_ms = timeout_ms
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._pending_page: Any = None

    # -- lifecycle ---------------------------------------------------------

    def _ensure_started(self) -> None:
        if self._context is not None:
            return
        import os

        from playwright.sync_api import sync_playwright  # lazy: see module docstring

        self._playwright = sync_playwright().start()
        # Reuse the Chromium the image already installs for Selenium
        # (CHROME_BIN, see Dockerfile) instead of downloading a second copy.
        launch_kwargs: Dict[str, Any] = {"headless": True}
        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin and os.path.isfile(chrome_bin):
            launch_kwargs["executable_path"] = chrome_bin
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            user_agent=self._user_agent,
            # No stealth flags, no webdriver patch, no fingerprint spoofing.
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        self._context.set_default_navigation_timeout(self._timeout_ms)

    def close(self) -> None:
        self.close_page()
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    closer.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:  # noqa: BLE001
            pass
        self._context = self._browser = self._playwright = None

    # -- fetching ----------------------------------------------------------

    @staticmethod
    def _retry_after(headers: Dict[str, str]) -> Optional[float]:
        raw = (headers or {}).get("retry-after")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None  # HTTP-date form: let our own backoff decide instead

    def fetch(self, url: str) -> FetchResult:
        try:
            self._ensure_started()
        except Exception as exc:  # noqa: BLE001 — missing browser binaries, etc.
            return FetchResult(status=None, error=f"browser unavailable: {exc}")

        # The page must outlive this call: the returned document reads from it
        # lazily. The caller closes it with `close_page()` once extraction is
        # done — see VendorScrapeService._scrape_url's `finally`.
        self.close_page()
        try:
            self._pending_page = self._context.new_page()
        except Exception as exc:  # noqa: BLE001
            return FetchResult(status=None, error=str(exc))

        try:
            response = self._pending_page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:  # noqa: BLE001
            return FetchResult(status=None, error=str(exc))

        if response is None:
            return FetchResult(status=None, error="navigation produced no response")

        status = response.status
        if status >= 400:
            headers: Dict[str, str] = {}
            try:
                headers = {k.lower(): v for k, v in (response.headers or {}).items()}
            except Exception:  # noqa: BLE001
                pass
            return FetchResult(status=status, retry_after=self._retry_after(headers))

        return FetchResult(status=status, document=_PlaywrightPageDocument(self._pending_page))

    def close_page(self) -> None:
        """Close the page opened by the last :meth:`fetch`, if any."""
        page = getattr(self, "_pending_page", None)
        if page is not None:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
        self._pending_page = None


__all__ = [
    "FetchResult",
    "PageDocument",
    "PageFetcher",
    "PlaywrightPageFetcher",
    "StaticPageDocument",
]
