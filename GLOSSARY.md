# Glossary (web_scrape)

| Term | Meaning |
|---|---|
| Scraper | A package under `app/scrapers/` that reads one kind of site; registered in `app/scrapers/registry.py`. |
| pep-pedia | The peptide reference site we scrape for peptide pages and PK graphs. |
| Peptide row / CSV row | One scraped peptide, written to a CSV and then mapped into platform tables. |
| Mapper group A-F | The stages that turn a CSV row into table payloads: A lookups, B the peptide, C relations, D protocols and graph, E and F the remaining relations. |
| Insert order | The order groups must be written so foreign keys resolve (`docs/structured.md`). |
| Guarded insert | An insert that checks for an existing row first, so a re-run does not duplicate. |
| Fill-empty-only | The sync mode that writes a column only when the platform value is empty, never overwriting. |
| PK graph | The pharmacokinetics curve of a peptide (path, points, markers) stored in `peptide_graph`. |
| Legend | The labelled series descriptions of a PK graph. |
| Platform database | The peptides-platform database; its tables belong to Drizzle (XR-8). |
| Known undeclared column | A column written here that Drizzle does not declare (`KNOWN_UNDECLARED_COLUMNS`). |
| Contract snapshot | `contracts/platform-schema/<date>.json`, the platform columns this service uses. |
| Vendor / competitor | A shop whose public prices we read; never one of our own stores. |
| Vendor target | A stored description of a vendor to scrape (`vendor_scrape_targets`): URLs, optional selectors, review state. |
| Draft target | A URL-only target not yet approved; no run reads it. |
| URL-only discovery | Finding products from a bare store URL through the Woo Store API, Shopify, sitemaps or JSON-LD instead of selectors. |
| Observation | One price reading of one product at one time (`vendor_price_observations`), append-only. |
| Confidence | A 0-1 score of how well a reading matched; below the threshold it is held for review. |
| Delta review | Flagging a large move against the last accepted price instead of overwriting it. |
| Accepted-latest | The newest accepted observation per product; what the platform imports. |
| Politeness | robots.txt, a per-host rate limit, an honest User-Agent and no bypass of a refusal. |
| Gateway | The orchestrator service that fronts this API at `/web_scrape/*` and sends `X-Gateway-Token`. |
| Upstream | A service the gateway proxies to; this one is an upstream (XR-10). |
