"""Orchestrates competitor vendor scraping (peptides-platform#288).

Order of operations per URL, and the order matters:

1. **robots.txt** — asked *before* a browser is pointed at the URL. A
   disallowed path is never loaded.
2. **Rate limit** — per host, at least the configured floor, at least the
   site's own ``Crawl-delay``.
3. **Fetch** — honest User-Agent, no stealth. 429/5xx backs off within a
   budget; 403 and an exhausted budget end that host for the run.
4. **Extract** — selectors from configuration, values parsed conservatively.
5. **Score** — on what matched, not on whether the run completed.
6. **Review** — a big move against the last *accepted* price flags rather than
   overwrites.
7. **Persist** — append-only, with the confidence and the review status.

Every collaborator (fetcher, robots policy, rate limiter, repository, clock)
is injected, so the whole flow is exercised in tests with no network, no
browser and no database.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Iterable, List, Optional, Sequence
from urllib.parse import urlsplit

from src.core.vendor_models import (
    ReviewStatus,
    ScrapeStatus,
    VendorObservation,
    VendorScrapeReport,
    VendorTarget,
)
from src.extractors.vendor_listing import VendorListingExtractor
from src.infrastructure.playwright_fetcher import FetchResult, PageFetcher
from src.infrastructure.rate_limiter import HostRateLimiter
from src.infrastructure.robots import RobotsPolicy
from src.services.vendor_confidence import DeltaReviewer, score_confidence

logger = logging.getLogger(__name__)


def _host_of(url: str) -> str:
    return urlsplit(url).netloc.lower()


class VendorScrapeService:
    """Runs one competitor scrape pass over a set of targets."""

    def __init__(
        self,
        fetcher: PageFetcher,
        robots: RobotsPolicy,
        rate_limiter: HostRateLimiter,
        reviewer: DeltaReviewer,
        repository=None,
        extractor: Optional[VendorListingExtractor] = None,
        max_retries: int = 2,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._fetcher = fetcher
        self._robots = robots
        self._limiter = rate_limiter
        self._reviewer = reviewer
        #: Optional: a dry run (or a test) passes ``None`` and nothing is written.
        self._repo = repository
        self._extractor = extractor or VendorListingExtractor()
        self._max_retries = max(0, max_retries)
        self._clock = clock

    # -- public ------------------------------------------------------------

    def run(
        self, targets: Sequence[VendorTarget], limit_per_target: Optional[int] = None
    ) -> VendorScrapeReport:
        report = VendorScrapeReport(started_at=self._clock())
        try:
            for target in targets:
                if not target.enabled:
                    logger.info("Vendor target %s is disabled — skipping.", target.slug)
                    continue
                report.observations.extend(self._run_target(target, limit_per_target))
        finally:
            try:
                self._fetcher.close()
            except Exception:  # noqa: BLE001
                logger.debug("Fetcher close failed", exc_info=True)
            report.finished_at = self._clock()
        return report

    # -- per target --------------------------------------------------------

    def _urls_for(self, target: VendorTarget, limit: Optional[int]) -> List[str]:
        urls = list(target.product_urls)
        caps = [c for c in (target.max_products_per_run, limit) if c]
        if caps:
            urls = urls[: min(caps)]
        return urls

    def _run_target(
        self, target: VendorTarget, limit: Optional[int]
    ) -> Iterable[VendorObservation]:
        observations: List[VendorObservation] = []
        for url in self._urls_for(target, limit):
            host = _host_of(url)

            # A host that already refused us is not asked again this run.
            if self._limiter.should_abandon(host):
                observations.append(
                    self._failed(
                        target,
                        url,
                        ScrapeStatus.SKIPPED,
                        self._limiter.abandon_reason(host) or "host abandoned this run",
                    )
                )
                continue

            observations.append(self._scrape_url(target, url))
        return observations

    # -- per URL -----------------------------------------------------------

    def _scrape_url(self, target: VendorTarget, url: str) -> VendorObservation:
        host = _host_of(url)

        # 1. robots.txt, before anything is fetched.
        if not self._robots.is_allowed(url):
            logger.info("robots.txt disallows %s for our user-agent — not fetching.", url)
            return self._failed(
                target,
                url,
                ScrapeStatus.ROBOTS_DISALLOWED,
                "robots.txt disallows this path for our user-agent",
            )

        # 2. Pace ourselves: our floor, the target's override, and the site's
        #    own Crawl-delay, whichever is slowest.
        self._limiter.set_interval(host, target.min_request_interval_seconds)
        crawl_delay = self._robots.crawl_delay(url)
        if crawl_delay:
            self._limiter.set_interval(host, crawl_delay)

        result: Optional[FetchResult] = None
        attempts = self._max_retries + 1
        for _ in range(attempts):
            self._limiter.wait(host)
            result = self._fetcher.fetch(url)

            if result.refused:
                self._limiter.note_blocked(host, f"HTTP {result.status}")
                self._close_page()
                return self._failed(
                    target, url, ScrapeStatus.BLOCKED, f"site refused with HTTP {result.status}"
                )

            if result.throttled:
                self._close_page()
                self._limiter.note_throttled(host, result.retry_after)
                if self._limiter.should_abandon(host):
                    return self._failed(
                        target,
                        url,
                        ScrapeStatus.BLOCKED,
                        self._limiter.abandon_reason(host) or "throttled repeatedly",
                    )
                continue

            break

        if result is None:
            return self._failed(target, url, ScrapeStatus.ERROR, "no fetch attempted")

        if not result.ok:
            self._close_page()
            detail = result.error or f"HTTP {result.status}"
            status = ScrapeStatus.BLOCKED if result.throttled else ScrapeStatus.ERROR
            return self._failed(target, url, status, detail)

        self._limiter.note_success(host)

        # 3-6. Extract, score, review.
        try:
            fields = self._extractor.extract(result.document, target, url)
        except Exception as exc:  # noqa: BLE001 — a selector bug is not a run-ender
            logger.exception("Extraction failed for %s", url)
            return self._failed(target, url, ScrapeStatus.ERROR, f"extraction failed: {exc}")
        finally:
            self._close_page()

        breakdown = score_confidence(fields, target)
        observation = VendorObservation(
            vendor=target.slug,
            url=url,
            observed_at=self._clock(),
            status=ScrapeStatus.OK,
            product_name=fields.product_name,
            price=fields.price,
            currency=fields.currency,
            stock_status=fields.stock_status,
            coa_url=fields.coa_url,
            confidence=breakdown.score,
            confidence_breakdown=breakdown.to_dict(),
        )

        previous = self._previous_accepted(target.slug, url)
        decision = self._reviewer.assess(observation, previous)
        observation.review_status = decision.status
        observation.review_reason = decision.reason
        observation.review_note = decision.note

        if decision.status is not ReviewStatus.ACCEPTED:
            logger.warning(
                "Flagged %s (%s): %s", url, decision.reason.value if decision.reason else "?", decision.note
            )

        self._persist(observation)
        return observation

    # -- helpers -----------------------------------------------------------

    def _close_page(self) -> None:
        closer = getattr(self._fetcher, "close_page", None)
        if callable(closer):
            try:
                closer()
            except Exception:  # noqa: BLE001
                logger.debug("close_page failed", exc_info=True)

    def _failed(
        self, target: VendorTarget, url: str, status: ScrapeStatus, detail: str
    ) -> VendorObservation:
        """A non-result. No price, no stock, no placeholder — just the reason.

        Stored all the same: "we were told not to look" and "they blocked us"
        are facts an operator needs, and a silent gap in the data is not.
        """
        observation = VendorObservation(
            vendor=target.slug,
            url=url,
            observed_at=self._clock(),
            status=status,
            confidence=0.0,
            review_status=ReviewStatus.FLAGGED,
            review_note=detail,
            failure_detail=detail,
        )
        self._persist(observation)
        return observation

    def _previous_accepted(self, vendor: str, url: str) -> Optional[VendorObservation]:
        if self._repo is None:
            return None
        try:
            return self._repo.latest_accepted(vendor, url)
        except Exception:  # noqa: BLE001 — a DB hiccup must not fabricate "no previous"
            logger.exception("Could not read the last accepted price for %s", url)
            # Treat an unreadable history as "unknown", which the reviewer
            # handles by accepting only on its own merits. Raising here would
            # lose the whole run over one query.
            return None

    def _persist(self, observation: VendorObservation) -> None:
        if self._repo is None:
            return
        try:
            self._repo.insert(observation)
        except Exception:  # noqa: BLE001
            logger.exception("Could not store observation for %s", observation.url)
