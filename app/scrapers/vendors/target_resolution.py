"""Target-resolution steps of a vendor scrape: which URLs and readings a target yields.

A mixin of :class:`~app.scrapers.vendors.vendor_scraper.VendorScrapeService`,
split out to keep that file under 400 lines. It relies on the service's
``_failed`` helper, ``_fetcher``, ``_robots``, ``_limiter`` and
``_discovery_factory``.
"""

from __future__ import annotations

import logging
from urllib.parse import urldefrag, urljoin, urlsplit

from app.core.vendor_models import ProductReading, ScrapeStatus, VendorObservation, VendorTarget
from app.scrapers.vendors.discovery_result import DiscoveryResult

logger = logging.getLogger(__name__)


def _host_of(url: str) -> str:
    return urlsplit(url).netloc.lower()


class TargetResolutionMixin:
    # -- selector-free targets (AAD-1) -------------------------------------

    def _discover(
        self, target: VendorTarget, limit: int | None
    ) -> tuple[list[ProductReading], list[VendorObservation]]:
        """Every variant reading for a selector-free target, plus failures.

        The store URL (and a listing URL, if set) is crawled through the
        catalogue sources; each configured product URL is read on its own.
        Hosts are read one target at a time; the product cap is the smaller
        of the target's ``max_products_per_run`` and the run's limit.
        """
        seeds = [u for u in (target.store_url, target.listing_url) if u]
        if self._discovery_factory is None:
            where = (seeds + list(target.product_urls) + [target.slug])[0]
            return [], [
                self._failed(
                    target,
                    where,
                    ScrapeStatus.ERROR,
                    "selector-free discovery is not configured for this run",
                )
            ]
        caps = [c for c in (target.max_products_per_run, limit) if c]
        discovery = self._discovery_factory(target, min(caps) if caps else None)
        results: list[DiscoveryResult] = [discovery.discover(seed) for seed in seeds]
        results += [discovery.read_product(url) for url in target.product_urls]

        readings: list[ProductReading] = []
        failures: list[VendorObservation] = []
        seen: set = set()
        for result in results:
            logger.info(
                "Discovery %s via %s: %d products, %d variants, %d requests.",
                result.seed_url,
                result.method,
                result.products_seen,
                len(result.readings),
                result.requests_made,
            )
            for failure in result.failures:
                failures.append(self._failed(target, failure.url, failure.status, failure.detail))
            for reading in result.readings:
                if reading.url not in seen:
                    seen.add(reading.url)
                    readings.append(reading)
            if not result.readings and not result.failures:
                failures.append(
                    self._failed(
                        target,
                        result.seed_url,
                        ScrapeStatus.ERROR,
                        "; ".join(result.notes) or "no products found at this URL",
                    )
                )
        return readings, failures

    def _resolve_urls(self, target: VendorTarget, limit: int | None) -> tuple[list[str], list[VendorObservation]]:
        """Configured product URLs plus any discovered from the listing page.

        Returns ``(urls, failures)``; a listing page that could not be read
        (robots, refusal, error) is recorded as a failed observation against
        the listing URL itself, and the configured product URLs still run.
        """
        urls = list(target.product_urls)
        failures: list[VendorObservation] = []
        if target.listing_url and target.listing_link_selector:
            discovered, failure = self._discover_listing(target)
            if failure is not None:
                failures.append(failure)
            for url in discovered:
                if url not in urls:
                    urls.append(url)
        caps = [c for c in (target.max_products_per_run, limit) if c]
        if caps:
            urls = urls[: min(caps)]
        return urls, failures

    def _discover_listing(self, target: VendorTarget) -> tuple[list[str], VendorObservation | None]:
        """Read product links off a listing page, under the same gates as a product."""
        listing = target.listing_url or ""
        host = _host_of(listing)

        if not self._robots.is_allowed(listing):
            return [], self._failed(
                target,
                listing,
                ScrapeStatus.ROBOTS_DISALLOWED,
                "robots.txt disallows the listing page for our user-agent",
            )

        self._limiter.set_interval(host, target.min_request_interval_seconds)
        crawl_delay = self._robots.crawl_delay(listing)
        if crawl_delay:
            self._limiter.set_interval(host, crawl_delay)
        self._limiter.wait(host)

        result = self._fetcher.fetch(listing)
        try:
            if result.refused:
                self._limiter.note_blocked(host, f"HTTP {result.status}")
                return [], self._failed(
                    target, listing, ScrapeStatus.BLOCKED, f"site refused with HTTP {result.status}"
                )
            if not result.ok:
                if result.throttled:
                    self._limiter.note_throttled(host, result.retry_after)
                detail = result.error or f"HTTP {result.status}"
                return [], self._failed(target, listing, ScrapeStatus.ERROR, f"listing page: {detail}")
            self._limiter.note_success(host)

            enumerate_links = getattr(result.document, "query_all_attr", None)
            if not callable(enumerate_links):
                return [], self._failed(target, listing, ScrapeStatus.ERROR, "fetcher cannot enumerate listing links")
            hrefs = enumerate_links(target.listing_link_selector, "href") or []
        finally:
            self._close_page()

        found: list[str] = []
        for href in hrefs:
            absolute, _ = urldefrag(urljoin(listing, href))
            parsed = urlsplit(absolute)
            # Same host only: a listing page linking to another site does not
            # make that site a target we agreed to read.
            if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != host:
                continue
            if absolute != listing and absolute not in found:
                found.append(absolute)
        logger.info("Listing %s yielded %d product links.", listing, len(found))
        return found, None
