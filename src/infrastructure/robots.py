"""robots.txt policy for competitor scraping (peptides-platform#288).

We are reading other companies' websites. The first rule we hold ourselves to
is the one they can actually state machine-readably: ``robots.txt``. This
module is the only thing that decides whether a URL may be fetched, and
:class:`~src.services.vendor_scraper.VendorScrapeService` asks it *before*
opening a browser — a disallowed path is never loaded at all, not loaded and
then discarded.

Two decisions worth stating explicitly:

* **Unfetchable robots.txt means "do not crawl".** A 4xx means the site
  published no rules, which conventionally allows everything. A 5xx, a
  timeout, or a connection error means we do not know what the rules are, and
  the safe reading of "I don't know" is "don't". That is the behaviour major
  crawlers adopt and it is the one we can defend.
* **Crawl-delay is honoured**, and it raises our per-host delay; it can never
  lower the politeness floor we set ourselves.

The fetcher is injected, so tests exercise every branch without network
access.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

#: ``(status_code, body_text)``. ``status_code`` is ``None`` for a transport
#: failure (DNS, timeout, reset) — indistinguishable from a 5xx for our
#: purposes: we do not know the rules, so we do not crawl.
RobotsFetchResult = Tuple[Optional[int], str]
RobotsFetcher = Callable[[str], RobotsFetchResult]


def default_robots_fetcher(url: str, *, timeout: float = 10.0, user_agent: str = "") -> RobotsFetchResult:
    """Fetch robots.txt with ``requests``, announcing who we are."""
    import requests  # imported here so the module stays importable without it

    headers = {"User-Agent": user_agent} if user_agent else {}
    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
    except Exception as exc:  # noqa: BLE001 — any transport failure is "unknown"
        logger.warning("robots.txt fetch failed for %s: %s", url, exc)
        return None, ""
    return resp.status_code, resp.text or ""


@dataclass
class _CachedRobots:
    parser: Optional[RobotFileParser]
    #: True when we could not establish the rules and must refuse everything.
    unknown: bool
    fetched_at: float


class RobotsPolicy:
    """Per-host robots.txt cache and allow/deny decisions.

    Args:
        user_agent: the exact User-Agent we send, so the rules that apply to
            us are the ones we evaluate against.
        fetcher: ``(url) -> (status_code | None, body)``.
        ttl_seconds: how long a parsed robots.txt is reused.
    """

    def __init__(
        self,
        user_agent: str,
        fetcher: Optional[RobotsFetcher] = None,
        ttl_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._user_agent = user_agent
        self._fetcher = fetcher or (lambda url: default_robots_fetcher(url, user_agent=user_agent))
        self._ttl = ttl_seconds
        self._clock = clock
        self._cache: Dict[str, _CachedRobots] = {}

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, "", "", ""))

    def _load(self, origin: str) -> _CachedRobots:
        cached = self._cache.get(origin)
        now = self._clock()
        if cached is not None and (now - cached.fetched_at) < self._ttl:
            return cached

        status, body = self._fetcher(f"{origin}/robots.txt")

        if status is not None and 200 <= status < 300:
            parser = RobotFileParser()
            parser.parse(body.splitlines())
            entry = _CachedRobots(parser=parser, unknown=False, fetched_at=now)
        elif status is not None and 400 <= status < 500:
            # No rules published — conventionally, everything is allowed.
            entry = _CachedRobots(parser=None, unknown=False, fetched_at=now)
        else:
            # 5xx, 3xx loop, or transport failure: rules unknown -> refuse.
            logger.warning(
                "robots.txt for %s unavailable (status=%s) — treating every path as disallowed.",
                origin,
                status,
            )
            entry = _CachedRobots(parser=None, unknown=True, fetched_at=now)

        self._cache[origin] = entry
        return entry

    # -- public ------------------------------------------------------------

    def is_allowed(self, url: str) -> bool:
        """True only when robots.txt positively permits this path for us."""
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return False

        entry = self._load(self._origin(url))
        if entry.unknown:
            return False
        if entry.parser is None:
            return True
        return bool(entry.parser.can_fetch(self._user_agent, url))

    def crawl_delay(self, url: str) -> Optional[float]:
        """The site's requested Crawl-delay for us, in seconds, if any."""
        entry = self._load(self._origin(url))
        if entry.parser is None:
            return None
        try:
            delay = entry.parser.crawl_delay(self._user_agent)
        except Exception:  # noqa: BLE001 — a malformed directive is just "no delay"
            return None
        if delay is None:
            return None
        try:
            return float(delay)
        except (TypeError, ValueError):
            return None
