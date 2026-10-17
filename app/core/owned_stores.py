"""Our own stores, which are never competitor targets (AAD-1, AAD-2).

The platform tells its own stores apart from competitors with the
``OWNED_STORE_VENDORS`` env list (arcane, ruo, bulk, moglabs). The scraper
mirrors it, plus the stores' domains, so a competitor target can never be
pointed at one of our own shops: their prices come in through the store
import, and mixing the two would make our stores look like competitors of
themselves.

Read from settings on every call so tests (and an operator) can change the
lists without a re-import.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit


def _split(raw: str | None) -> set[str]:
    return {item.strip().lower() for item in (raw or "").split(",") if item.strip()}


def owned_domains() -> set[str]:
    from app.core.config import settings

    return {d.lstrip(".").removeprefix("www.") for d in _split(getattr(settings, "OWNED_STORE_DOMAINS", ""))}


def owned_slugs() -> set[str]:
    from app.core.config import settings

    return _split(getattr(settings, "OWNED_STORE_VENDORS", ""))


def is_owned_host(host: str | None) -> bool:
    """True for one of our domains or any subdomain of one."""
    name = (host or "").strip().strip("[]").rstrip(".").lower()
    if not name:
        return False
    return any(name == d or name.endswith("." + d) for d in owned_domains())


def is_owned_url(url: str | None) -> bool:
    try:
        return is_owned_host(urlsplit(url or "").hostname)
    except ValueError:
        return False


def is_owned_slug(slug: str | None) -> bool:
    return bool(slug) and str(slug).strip().lower() in owned_slugs()


def owned_reason(urls: Iterable[str | None], slugs: Iterable[str | None] = ()) -> str | None:
    """Why this target is one of our own stores, or ``None`` if it is not."""
    for url in urls:
        if url and is_owned_url(url):
            return f"'{urlsplit(url).hostname}' is one of our own stores, not a competitor"
    for slug in slugs:
        if is_owned_slug(slug):
            return f"'{slug}' is one of our own store vendors, not a competitor"
    return None


__all__ = ["is_owned_host", "is_owned_slug", "is_owned_url", "owned_domains", "owned_reason", "owned_slugs"]
