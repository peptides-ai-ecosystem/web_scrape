"""Per-host rate limiting and backoff for competitor scraping (#288).

One knob per host, not one global knob: hitting six vendors once a second each
is polite, hitting one vendor six times a second is not.

The limiter also owns the *give up* decision. On repeated 429 / 5xx the
correct behaviour is to back off and then stop — :meth:`should_abandon`
reports when a host has spent its retry budget so the caller records the block
and moves on. Nothing here retries forever, rotates an identity, or changes
the User-Agent to get past a refusal.

``clock`` and ``sleeper`` are injected so tests run instantly and never sleep.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


class HostRateLimiter:
    """Enforce a minimum interval between requests to each host.

    Args:
        default_interval: politeness floor in seconds, applied to every host.
        max_strikes: how many throttle responses (429/5xx) a host may return
            before :meth:`should_abandon` says stop.
        base_backoff: first backoff in seconds; doubles per strike.
        max_backoff: cap so a hostile ``Retry-After`` cannot hang a run.
    """

    def __init__(
        self,
        default_interval: float = 5.0,
        max_strikes: int = 2,
        base_backoff: float = 30.0,
        max_backoff: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self._default_interval = max(0.0, default_interval)
        self._max_strikes = max(0, max_strikes)
        self._base_backoff = max(0.0, base_backoff)
        self._max_backoff = max(0.0, max_backoff)
        self._clock = clock
        self._sleep = sleeper
        self._last_request: Dict[str, float] = {}
        self._intervals: Dict[str, float] = {}
        self._strikes: Dict[str, int] = {}
        self._abandoned: Dict[str, str] = {}

    # -- configuration -----------------------------------------------------

    def set_interval(self, host: str, interval: float) -> None:
        """Raise this host's interval. Never lowers the politeness floor."""
        effective = max(self._default_interval, float(interval or 0.0))
        self._intervals[host] = max(self._intervals.get(host, 0.0), effective)

    def interval_for(self, host: str) -> float:
        return max(self._default_interval, self._intervals.get(host, 0.0))

    # -- pacing ------------------------------------------------------------

    def wait(self, host: str) -> float:
        """Block until this host may be called again. Returns seconds slept."""
        interval = self.interval_for(host)
        last = self._last_request.get(host)
        slept = 0.0
        if last is not None:
            elapsed = self._clock() - last
            remaining = interval - elapsed
            if remaining > 0:
                self._sleep(remaining)
                slept = remaining
        self._last_request[host] = self._clock()
        return slept

    # -- backoff -----------------------------------------------------------

    def note_throttled(self, host: str, retry_after: Optional[float] = None) -> float:
        """Record a 429/5xx from ``host`` and sleep for the backoff.

        Returns the seconds slept. After ``max_strikes`` the host is marked
        abandoned for the rest of the run.
        """
        strikes = self._strikes.get(host, 0) + 1
        self._strikes[host] = strikes

        backoff = self._base_backoff * (2 ** (strikes - 1))
        if retry_after is not None:
            try:
                backoff = max(backoff, float(retry_after))
            except (TypeError, ValueError):
                pass
        backoff = min(backoff, self._max_backoff)

        if strikes > self._max_strikes:
            self._abandoned[host] = (
                f"host returned {strikes} throttle/error responses; "
                "abandoned for this run"
            )
            logger.warning("Abandoning %s for this run after %d throttled responses.", host, strikes)
            return 0.0

        logger.info("Backing off %ss from %s (strike %d).", backoff, host, strikes)
        if backoff > 0:
            self._sleep(backoff)
        # Count the backoff as the most recent contact so `wait` does not
        # immediately fire another request on top of it.
        self._last_request[host] = self._clock()
        return backoff

    def note_blocked(self, host: str, reason: str) -> None:
        """Record an outright refusal (403 / bot wall) and stop this host.

        There is no second branch here on purpose. We do not solve CAPTCHAs,
        swap identities, or retry behind a different fingerprint; a site that
        says no is recorded as having said no.
        """
        self._abandoned[host] = reason
        logger.warning("Host %s refused us: %s. Not retrying.", host, reason)

    def note_success(self, host: str) -> None:
        self._strikes.pop(host, None)

    def should_abandon(self, host: str) -> bool:
        return host in self._abandoned

    def abandon_reason(self, host: str) -> Optional[str]:
        return self._abandoned.get(host)
