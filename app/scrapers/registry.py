"""Name -> scraper descriptor. Adding a site is one new package and one line here."""

from app.scrapers.base import ScraperInfo

SCRAPERS: dict[str, ScraperInfo] = {
    "pep_pedia": ScraperInfo(
        name="pep_pedia",
        summary="pep-pedia.org peptide pages -> CSV -> platform peptide and PK-graph tables",
        discover="app.scrapers.pep_pedia.crawl_peptide_urls.crawl_peptide_urls",
        fetch="app.infrastructure.webdriver_factory.WebDriverFactory",
        extract=(
            "app.scrapers.pep_pedia.page_scraper.PageScraper",
            "app.scrapers.pep_pedia.extractors.graph.GraphExtractor",
        ),
        controller="app.controllers.pep_pedia_sync_controller.PepPediaSyncController",
        writes="platform",
    ),
    "vendors": ScraperInfo(
        name="vendors",
        summary="competitor product pages -> price observations awaiting review",
        discover="app.scrapers.vendors.url_discovery.UrlOnlyDiscovery",
        fetch="app.infrastructure.playwright_fetcher.PlaywrightPageFetcher",
        extract=(
            "app.scrapers.vendors.extractors.vendor_listing.VendorListingExtractor",
            "app.scrapers.vendors.extractors.store_api",
            "app.scrapers.vendors.extractors.structured_data",
        ),
        controller="app.controllers.vendor_scrape_controller.VendorScrapeController",
        writes="own",
        own_tables=("vendor_scrape_targets", "vendor_price_observations"),
    ),
}


def get_scraper(name: str) -> ScraperInfo:
    """The descriptor for ``name``; ``KeyError`` for an unknown scraper."""
    return SCRAPERS[name]
