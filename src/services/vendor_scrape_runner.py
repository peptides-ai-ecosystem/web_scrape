"""Wiring for a competitor scrape run (peptides-platform#288).

One place that builds a :class:`~src.services.vendor_scraper.VendorScrapeService`
from settings, so the nightly cron and the on-demand API trigger run exactly
the same pipeline with exactly the same guards. A guard that only the cron
honours is not a guard.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from src.config import (
    VENDOR_MIN_CONFIDENCE,
    VENDOR_PRICE_DELTA_THRESHOLD,
    VENDOR_PRODUCTS_PUBLISH_ENABLED,
    VENDOR_SCRAPE_BACKOFF_SECONDS,
    VENDOR_SCRAPE_MAX_RETRIES,
    VENDOR_SCRAPE_MIN_INTERVAL_SECONDS,
    VENDOR_SCRAPE_TIMEOUT_MS,
    VENDOR_SCRAPER_USER_AGENT,
)
from src.core.vendor_models import VendorTarget
from src.infrastructure.db.connection import DbConnection
from src.infrastructure.db.repositories import VendorObservationRepository
from src.infrastructure.playwright_fetcher import PlaywrightPageFetcher
from src.infrastructure.rate_limiter import HostRateLimiter
from src.infrastructure.robots import RobotsPolicy
from src.infrastructure.vendor_targets import load_targets
from src.services.vendor_confidence import DeltaReviewer
from src.services.vendor_products_publisher import VendorProductsPublisher
from src.services.vendor_scraper import VendorScrapeService

logger = logging.getLogger(__name__)


def select_targets(
    vendors: Optional[Sequence[str]] = None, *, include_disabled: bool = False
) -> List[VendorTarget]:
    """Configured targets, optionally narrowed to specific slugs.

    A slug that is not configured is dropped with a warning rather than
    guessed at — "scrape competitorX" for a competitorX we have no selectors
    for would produce a confident-looking empty result.
    """
    targets = load_targets(include_disabled=include_disabled)
    if not vendors:
        return targets

    wanted = {v.strip().lower() for v in vendors if v and v.strip()}
    by_slug = {t.slug.lower(): t for t in targets}
    missing = wanted - set(by_slug)
    for slug in sorted(missing):
        logger.warning("Requested vendor '%s' is not in the targets config — ignored.", slug)
    return [by_slug[s] for s in sorted(wanted & set(by_slug))]


def build_service(repository=None) -> VendorScrapeService:
    """Assemble the pipeline from settings."""
    user_agent = VENDOR_SCRAPER_USER_AGENT
    return VendorScrapeService(
        fetcher=PlaywrightPageFetcher(
            user_agent=user_agent, timeout_ms=VENDOR_SCRAPE_TIMEOUT_MS
        ),
        # Same user-agent string the fetcher sends: obeying robots rules
        # written for a different agent would be theatre.
        robots=RobotsPolicy(user_agent=user_agent),
        rate_limiter=HostRateLimiter(
            default_interval=VENDOR_SCRAPE_MIN_INTERVAL_SECONDS,
            max_strikes=VENDOR_SCRAPE_MAX_RETRIES,
            base_backoff=VENDOR_SCRAPE_BACKOFF_SECONDS,
        ),
        reviewer=DeltaReviewer(
            min_confidence=VENDOR_MIN_CONFIDENCE,
            delta_threshold=VENDOR_PRICE_DELTA_THRESHOLD,
        ),
        repository=repository,
        max_retries=VENDOR_SCRAPE_MAX_RETRIES,
    )


def run_vendor_scrape(
    vendors: Optional[Sequence[str]] = None, limit_per_vendor: Optional[int] = None
) -> Dict[str, Any]:
    """Run one pass and return a JSON-safe report.

    Used by both ``POST /api/v1/vendors/scrape`` and the nightly cron.
    """
    targets = select_targets(vendors)
    if not targets:
        logger.warning("No enabled vendor targets configured — nothing to scrape.")
        return {
            "urls_processed": 0,
            "status_counts": {},
            "review_counts": {},
            "observations": [],
            "note": "no enabled vendor targets configured",
        }

    db_url = os.getenv("DATABASE_URL")
    connection: Optional[DbConnection] = None
    repository = None
    if db_url:
        connection = DbConnection(db_url)
        repository = VendorObservationRepository(connection)
    else:
        # A run with nowhere to store results is still useful (the report comes
        # back on the job), but say so rather than appearing to persist.
        logger.warning("DATABASE_URL not set — vendor observations will not be stored.")

    try:
        service = build_service(repository=repository)
        report = service.run(targets, limit_per_target=limit_per_vendor)
    finally:
        if connection is not None:
            connection.close()

    payload = report.to_dict()
    payload["persisted"] = repository is not None

    # The onward write into the platform's vendor_products is a documented
    # no-op; calling it keeps the seam exercised and its reason visible.
    publisher = VendorProductsPublisher(enabled=VENDOR_PRODUCTS_PUBLISH_ENABLED)
    payload["vendor_products_publish"] = publisher.publish(report.observations).to_dict()

    return payload
