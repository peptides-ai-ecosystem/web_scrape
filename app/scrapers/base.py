"""What every scraper hosted in this service declares.

A scraper is one package under ``app/scrapers/`` that reads one kind of site.
It does not import FastAPI and does not write SQL: its controller
(``app/controllers/``) calls the scraper, then a sync service or a
repository. Shared fetch code (Playwright, the polite HTTP client, robots.txt,
the rate limiter, the SSRF guard) stays in ``app/infrastructure/``.

The two scrapers today have different shapes, so the descriptor records the
pieces each one has rather than forcing one call signature:

* ``discover`` - where the URLs come from;
* ``fetch`` - the browser or HTTP client that loads a page;
* ``extract`` - the code that turns a loaded page into rows;
* ``writes`` - where the rows end up (platform tables through ``app/services/sync``,
  or this service's own tables through ``app/repositories``).

``app/scrapers/registry.py`` maps a name to its descriptor; ``docs/adding-a-scraper.md``
is the checklist for a new one.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScraperInfo:
    """One hosted scraper. Every dotted path must import (tests/ops/test_scraper_registry.py)."""

    name: str
    summary: str
    #: Dotted path of the callable or class that finds the URLs to read.
    discover: str
    #: Dotted path of the page loader (browser or HTTP client).
    fetch: str
    #: Dotted path of the extractor(s) that turn a page into rows.
    extract: tuple[str, ...]
    #: Dotted path of the controller the HTTP routes call.
    controller: str
    #: Where rows are written: "platform" (XR-8, Drizzle-owned) or "own".
    writes: str
    #: Tables this scraper owns (an Alembic revision each); empty for platform writers.
    own_tables: tuple[str, ...] = field(default_factory=tuple)
