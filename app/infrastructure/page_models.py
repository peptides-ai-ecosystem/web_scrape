"""Page and fetch-result types shared by the vendor scrapers (#288).

``PageDocument`` is the seam every extractor is written against, ``FetchResult``
what a fetch returns, ``PageFetcher`` the protocol the scrape service injects and
``StaticPageDocument`` the browser-free implementation tests and replays use.
Split out of playwright_fetcher.py so that module holds only the browser code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

# ---------------------------------------------------------------------------
# The seam every extractor is written against
# ---------------------------------------------------------------------------


class PageDocument(Protocol):
    """The narrow slice of a rendered page the extractor needs.

    Keeping it this small is what lets the whole extraction/confidence layer
    be tested with a dictionary instead of a browser.
    """

    def query_text(self, selector: str) -> str | None:
        """Visible text of the first match, or ``None``."""

    def query_attr(self, selector: str, attr: str) -> str | None:
        """Attribute of the first match, or ``None``."""


@dataclass
class FetchResult:
    """Outcome of loading one URL."""

    #: HTTP status of the main document. ``None`` when navigation never
    #: produced a response (DNS failure, timeout, browser crash).
    status: int | None
    document: PageDocument | None = None
    error: str | None = None
    #: ``Retry-After`` in seconds if the site sent one we could parse.
    retry_after: float | None = None

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


@dataclass
class StaticPageDocument:
    """A :class:`PageDocument` backed by two plain dicts.

    Used by tests, and by anything that has already captured a page's fields
    (a fixture, a replayed extraction) and wants to re-run scoring over it
    without a browser.
    """

    texts: dict[str, str] = field(default_factory=dict)
    attrs: dict[str, dict[str, str]] = field(default_factory=dict)
    #: ``{selector: {attr: [value, ...]}}`` for :meth:`query_all_attr`.
    attr_lists: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    #: Raw HTML for :meth:`html` (selector-free discovery).
    raw_html: str | None = None

    def html(self) -> str | None:
        return self.raw_html

    def query_text(self, selector: str) -> str | None:
        value = self.texts.get(selector)
        return value.strip() if isinstance(value, str) and value.strip() else None

    def query_attr(self, selector: str, attr: str) -> str | None:
        value = (self.attrs.get(selector) or {}).get(attr)
        return value.strip() if isinstance(value, str) and value.strip() else None

    def query_all_attr(self, selector: str, attr: str) -> list[str]:
        values = (self.attr_lists.get(selector) or {}).get(attr) or []
        return [v.strip() for v in values if isinstance(v, str) and v.strip()]
