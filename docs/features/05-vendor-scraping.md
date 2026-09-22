# Feature: Competitor Vendor Price Scraping

> **Issue**: peptides-platform#288 (depends on #263 / #10)
>
> **Modules**: `src/core/vendor_models.py`, `src/infrastructure/{robots,rate_limiter,playwright_fetcher,vendor_targets}.py`,
> `src/extractors/vendor_listing.py`, `src/services/{vendor_scraper,vendor_confidence,vendor_scrape_runner,vendor_products_publisher}.py`,
> `src/infrastructure/db/repositories/vendor_observation.py`, `src/api/v1/endpoints/vendors.py`
>
> **Entry points**: `POST /api/v1/vendors/scrape` (on demand) and the nightly APScheduler cron
>
> **Migration**: `migration_vendor_price_observations.sql`

---

## 1. Business Logic

### 1.1 Purpose

Own-vendor prices come from the WooCommerce sync (peptides-platform#263). **Competitor** prices have no API,
so they have to be read off the vendors' own web pages. This feature navigates a configured list of
competitor product pages with Playwright and extracts **price**, **stock status** and **COA link**, scores how
much it trusts each reading, and puts anything doubtful in a review queue instead of publishing it.

### 1.2 What problem does it solve?

- Competitor pricing was previously hand-curated, which goes stale silently.
- A scraped price is a *guess about someone else's website*. Layouts change without warning, and a wrong
  price that looks authoritative is worse than no price. The pipeline is therefore built around admitting
  when it does not know.

### 1.3 Key rules

| Rule | Description |
|---|---|
| **robots.txt first** | Checked **before** the browser is pointed at a URL. A disallowed path is never loaded. An unreachable robots.txt (5xx / timeout) means *disallowed* — we do not crawl on rules we could not read. |
| **Per-host rate limit** | The effective delay is the largest of the global floor, the target's own setting, and the site's `Crawl-delay`. Limits are per host, not global. |
| **Back off, then stop** | 429/5xx backs off exponentially for a bounded number of strikes, then abandons the host for the run. 403/401/451 stops immediately. |
| **No evasion** | Honest User-Agent with a contact URL, no fingerprint masking, no proxy rotation, no CAPTCHA solving. A site that blocks us is recorded as having blocked us. |
| **Targets are configuration** | A site is added, paused (`"enabled": false`) or deleted by editing one JSON file. Nothing is hardcoded, so a site can always be removed without a deploy. |
| **Confidence from matches** | Scored on which selectors actually matched and how far down the fallback list — never on whether the run completed. |
| **Big deltas flag, not overwrite** | A price move beyond the threshold is stored **flagged**; the last accepted value stays current until a human resolves it. |
| **Nothing rather than a placeholder** | An unreadable price is `NULL`, never `0`. Unrecognised stock text is `NULL`, never `instock`. |

---

## 2. Configuration

### 2.1 Targets file

Copy `config/vendor_targets.example.json` to the path in `VENDOR_TARGETS_FILE`
(default `config/vendor_targets.json`, git-ignored — the real competitor list is deployment-owned).

```json
{
  "targets": [
    {
      "slug": "example-vendor",
      "name": "Example Vendor",
      "enabled": true,
      "currency": "USD",
      "min_request_interval_seconds": 8.0,
      "max_products_per_run": 25,
      "product_urls": ["https://example.com/product/bpc-157-5mg"],
      "selectors": {
        "product_name": ["h1.product-title", "h1"],
        "price": ["[data-testid='product-price']", "p.price .amount"],
        "stock": ["p.stock", ".availability"],
        "coa": ["a[href*='coa']"]
      }
    }
  ]
}
```

Selector lists are **ordered**: index 0 is the element you believe is the real one, later entries are
fallbacks and score lower. A missing or malformed file means *no scraping at all*, not a crash and not a
hardcoded default.

### 2.2 Environment

See `.env.example` for the full list. The ones that change behaviour most:

| Variable | Default | Effect |
|---|---|---|
| `VENDOR_TARGETS_FILE` | `config/vendor_targets.json` | Where targets live |
| `VENDOR_SCRAPER_CONTACT_URL` | this repo's URL | Goes into the User-Agent |
| `VENDOR_SCRAPE_MIN_INTERVAL_SECONDS` | `5.0` | Politeness floor per host |
| `VENDOR_SCRAPE_MAX_RETRIES` | `2` | Throttle strikes before abandoning a host |
| `VENDOR_PRICE_DELTA_THRESHOLD` | `0.25` | Relative move that flags for review |
| `VENDOR_MIN_CONFIDENCE` | `0.6` | Below this, always flag |
| `VENDOR_SCRAPE_CRON_ENABLED` | `false` | Nightly cron on boot — opt in per environment |
| `VENDOR_SCRAPE_CRON_HOUR` / `_MINUTE` | `3` / `15` | When the nightly run fires |

---

## 3. Pipeline

```
target config
      │
      ▼
robots.txt  ──disallowed──►  observation(status=robots_disallowed)   [never fetched]
      │ allowed
      ▼
rate limit (max of floor, target, Crawl-delay)
      │
      ▼
Playwright fetch ──403──►  observation(status=blocked)               [host dropped for the run]
      │           ──429/5xx──► backoff ×N ──► observation(status=blocked)
      │ 200
      ▼
extract price / stock / COA / name   (conservative parsers, None over placeholders)
      │
      ▼
confidence = Σ(weight × fallback-discount) / Σ(weight of configured fields)
      │
      ▼
delta review vs last ACCEPTED observation
      │                    │
   accepted            flagged (no_price | low_confidence | price_delta | currency_changed)
      │                    │
      ▼                    ▼
        vendor_price_observations (append-only)
```

### 3.1 Confidence

Weights: `price 0.55`, `stock 0.20`, `coa 0.15`, `product_name 0.10`. Only fields the target actually
declares a selector for are in the denominator — a vendor with no COA selector is not penalised for having
no COA, because we never looked. A field matched on fallback selector #1 keeps 75% of its weight, #2+ keeps
50%.

A run can complete perfectly and still score 0: completion is not evidence.

### 3.2 Review

`DeltaReviewer` flags, in order:

1. `no_price` — nothing plausible on the page.
2. `low_confidence` — below `VENDOR_MIN_CONFIDENCE`.
3. `currency_changed` — a different currency is not a price move.
4. `price_delta` — relative move above `VENDOR_PRICE_DELTA_THRESHOLD`.

A flagged observation is **stored** (the evidence matters) but `latest_accepted()` will not return it, so it
cannot become the current price. Resolve one with
`POST /api/v1/vendors/observations/{id}/review`.

---

## 4. API

| Endpoint | Description |
|---|---|
| `GET /api/v1/vendors/targets` | Configured targets, plus the exact User-Agent we send |
| `POST /api/v1/vendors/scrape` | On-demand run; returns **202** and a `job_id` to poll on `/operations/job/{id}` |
| `GET /api/v1/vendors/observations/flagged` | The review queue |
| `POST /api/v1/vendors/observations/{id}/review` | `accept` or `reject` one flagged reading |
| `GET /api/v1/scheduler/vendor-scrape/status` | Nightly cron status |
| `POST /api/v1/scheduler/vendor-scrape/{start,pause,resume}` | Manage the nightly cron |

The on-demand endpoint and the cron call the same `run_vendor_scrape()`, so both are subject to the same
guards. A guard only the cron honours is not a guard.

---

## 5. Why this does **not** write to `vendor_products`

peptides-platform#288 asks for rows in `vendor_products` with `source = 'scraper'`. That write is **not
implemented**, and the full reasoning lives in the module docstring of
`src/services/vendor_products_publisher.py`. In short, four independent blockers:

1. **No reachable database.** `vendor_products` is in the peptides-platform database. This service has one
   `DATABASE_URL`, pointing at its own store, and no credentials or client for the platform's.
2. **No `source` column.** As of platform migration `0109`, `vendor_products` has no provenance column.
   `match_source` is *not* it — it records how `peptide_slug` was decided (`override`/`exact`/`alias`/
   `fuzzy`/`ignored`/`unmatched`), so writing `'scraper'` there would corrupt the admin's unmatched queue
   instead of marking provenance.
3. **The key is Woo-shaped.** `wc_product_id` is `NOT NULL` and the unique index is
   `(vendor, wc_product_id, wc_variation_id)`. A competitor page has no Woo product id, and synthesising one
   is exactly how a scraped guess becomes indistinguishable from a vendor's published price.
4. **#263 declared the table single-writer** ("written only by the sync"). Adding a second writer is that
   issue's owners' call, in their repo. This change loosens nothing: no column, no grant, no connection, no
   outbound write.

Accepted observations live in this service's own `vendor_price_observations` and are readable over the API
today. The platform-side changes that would unblock the direct write are enumerated in the publisher module.

---

## 6. Testing

```bash
uv run pytest src/tests/test_vendor_scraper.py -q
```

No network, no browser, no database: Playwright is never imported by the tests, robots responses are canned,
clocks and sleepers are injected, and the repository is an in-memory double.
