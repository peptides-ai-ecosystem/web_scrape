"""Single source of "now" for naive UTC timestamps (ADR 0010)."""

from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Naive UTC now: same value and ``.timestamp()`` as the deprecated ``datetime.utcnow()``."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
