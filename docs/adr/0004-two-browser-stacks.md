# 0004 - Two browser stacks stay, each with one job

Status: accepted (2026-10-18).

## Context
The pep-pedia scrape drives Selenium with Chromium and chromedriver (`app/infrastructure/webdriver_factory.py`, `webdriver-manager` as a local fallback). The vendor scraper uses Playwright (`app/infrastructure/playwright_fetcher.py`), which routes every request through the SSRF guard. Both run in the one runtime image, which carries Chromium; both read `CHROME_BIN`.

## Decision
Keep both for now. Selenium stays on the pep-pedia path, Playwright on the vendor path; new code uses Playwright. Moving pep-pedia to Playwright is a separate change with its own plan, not a drive-by. The Chromium-only test (`TestLocalFixtureSite`) runs for real in CI job `chromium-tests`.

## Consequences
Two driver dependencies and one browser to keep in the image. Open question for the owner: migrate pep-pedia to Playwright, or keep Selenium until the scrape is retired.
