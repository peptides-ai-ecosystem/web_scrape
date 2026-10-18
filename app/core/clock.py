"""Single source of "now" for naive UTC timestamps (ADR 0010)."""

from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """Naive UTC now: same value and ``.timestamp()`` as the deprecated naive-UTC call."""
    return datetime.now(UTC).replace(tzinfo=None)
