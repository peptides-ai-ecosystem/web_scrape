# Feature: Scrape a competitor from a URL only

> **Status**: shipped.

> **Modules**: `app/scrapers/vendors/url_discovery.py`, `app/scrapers/vendors/extractors/{store_api,structured_data}.py`,
> `app/infrastructure/polite_http.py`, `app/core/owned_stores.py`, and the URL-only parts of
> `app/services/{vendor_scraper,vendor_scrape_runner}.py` and `app/api/v1/endpoints/vendors.py`
>
> **Tests**: `tests/vendors/test_url_discovery.py` (offline; recorded responses in
> `tests/vendors/fixtures/url_discovery/`)

Before this, every competitor target needed hand-written CSS selectors per site (for example GL Peptides'
size button `button.min-w-16[aria-pressed="true"]`). Now an admin can give just a store URL. Selectors
remain as an optional override for sites the automatic readers cannot handle.

## 1. How a URL is read

A target with **no price selector** has `discovery_mode: "auto"`. Its `store_url` (and `listing_url`, if
set) is crawled; each `product_urls` entry is read on its own. Sources, in order:

| # | Source | Requests | What it gives |
|---|---|---|---|
| 1 | **WooCommerce Store API** `GET /wp-json/wc/store/v1/products?per_page=100&page=N` | 1 per 100 products, plus 1 per 100 variations (`?type=variation&include=…`) | name, SKU, price (minor units → decimal), currency, stock, **one reading per variation** with its size attribute |
| 2 | **Shopify** `GET /products.json?limit=250&page=N` | 1 per 250 products | every variant's title (size), price, availability, SKU |
| 3 | **Sitemaps**: robots.txt `Sitemap:` lines, `/sitemap_index.xml`, `/sitemap.xml`, `/wp-sitemap.xml`, `/product-sitemap.xml` | 1-5 sitemaps, then 1 per product page | product URLs; each page read for schema.org **JSON-LD** `Product` / `ProductGroup` (`hasVariant`) / `Offer` / `AggregateOffer`, then **microdata** (`itemprop="price"`), then **OpenGraph** (`product:price:amount`) |
| 4 | **Rendering** | 1 per page | a page whose static HTML has no structured price is loaded once in the browser (scripts on) and read again |

A **product URL** (`/product/<slug>/`, `/products/<handle>`) reads only that product: the Store API by
`?slug=`, Shopify's `/products/<handle>.json`, or the page itself. A **home or shop URL** reads the
catalogue. If no source works, the run records one `error` observation with the reason ("no Store API,
products.json, sitemap or structured price found; add CSS selectors to this target").

### Variants and sizes

Every variant/size is its own reading:

* `product_name` carries the size (`"Retatrutide 10mg"`): the platform import parses the size from the name.
  A size already in the name is not repeated; Shopify's `"Default Title"` is not a size.
* `variant_label` and `sku` are stored separately (new columns on `vendor_price_observations`), and
  `extraction_method` records which source was used (`woo_store_api`, `shopify_json`, `json_ld`, `microdata`,
  `opengraph`, or `selectors` for the old path).
* The observation `url` identifies the variant (`?attribute_pa_size=10mg` / `?variant=<id>` / `#variant=<sku>`),
  because the review gate and `accepted-latest` key on `(vendor, url)`. Two sizes never overwrite each other.

### Confidence

| Source | Confidence |
|---|---|
| Store API / products.json, size known | 0.95 |
| JSON-LD offer | 0.90 |
| microdata | 0.75 |
| OpenGraph | 0.65 |
| A price range ("from $29"), or several prices we cannot tell apart by size | 0.50 → **flagged** |
| A price whose name and variant carry no size (`10mg`, `5 ml`, `60 caps`…) — e.g. one Offer for the default size on a multi-size page | capped at 0.55 → **flagged** (the platform import matches by size and would refuse it) |

The usual review rules then apply unchanged: below `VENDOR_MIN_CONFIDENCE` (0.6) is flagged, a move beyond
`VENDOR_PRICE_DELTA_THRESHOLD` against the last accepted reading for that variant is flagged, and no price is
never stored as 0.

## 2. Politeness

All discovery requests go through `PoliteHttpClient`:

* **robots.txt first**, for every URL and every redirect hop (the Store API path is skipped when
  `/wp-json/` is disallowed). Unknown robots.txt (5xx / unreachable) means nothing is fetched.
* **SSRF guard** on every hop (public addresses only), redirects followed by hand.
* **One host at a time**: targets are read one after another; within a host at most
  `VENDOR_DISCOVERY_CONCURRENCY` (1-4, default 2) requests are in flight, and request starts are spaced by
  the per-host rate limit (`VENDOR_SCRAPE_MIN_INTERVAL_SECONDS`, the target's interval, robots `Crawl-delay`).
* **Caps**: `VENDOR_DISCOVERY_MAX_REQUESTS` (60) requests per target per run, `VENDOR_DISCOVERY_MAX_PRODUCTS`
  (200) products unless the target sets `max_products_per_run`, `VENDOR_DISCOVERY_TIMEOUT_SECONDS` (15) per
  request, 8 MB per response.
* **No retry storm**: each request is made once. 401/403/451 ends the host for the run; 429/5xx backs off
  through the limiter's strike budget and the request is not repeated.
* The same honest User-Agent as the browser path (`VENDOR_SCRAPER_USER_AGENT`).

## 3. Competitor vendors stay separate

* `POST /targets/from-url` creates a **draft** competitor target (`review_state: "draft"`,
  `kind: "competitor"`). Drafts are listed (and `draft_count` is returned) but **no run reads them**, named or
  not, until `POST /targets/{slug}/approve`. Any new target without a price selector starts as a draft,
  whether created through `from-url`, `POST /targets` or `PUT /targets/{slug}`. `PUT` never changes
  `review_state`.
* Targets configured with selectors by an admin are approved at once, as before; existing rows are backfilled
  `approved`.
* **Our own stores are refused**: a URL on `OWNED_STORE_DOMAINS` (default `arcanepeptides.com, ruo.bio,
  bulkpeptides.com, moglabs.bio`, subdomains included) or a slug / `platform_vendor_slug` in
  `OWNED_STORE_VENDORS` (default `arcane, ruo, bulk, bulkpeptides, moglabs`) gets **422** on create, update,
  from-url, approve and discover, and is skipped (`status: skipped`) if one is ever in a run.

## 4. API

| Endpoint | |
|---|---|
| `POST /api/v1/vendors/targets/from-url` | `{url, name?, slug?, currency?, platform_vendor_slug?, max_products_per_run?}` → 201 draft target. Slug defaults to the host (`www.glpeptides.is` → `glpeptides-is`). 409 duplicate, 422 own store / non-public URL |
| `POST /api/v1/vendors/targets/{slug}/approve` | `{approved_by?}` → the approved target. 404 unknown, 409 file target (always approved), 422 own store |
| `POST /api/v1/vendors/discover` | `{url, max_products (1-25, default 5), currency?}` → dry run: `method`, `products_seen`, `variants_found`, `priced`, `requests_made`, `notes`, `failures`, `readings[]`. Nothing stored, no browser. Paced like a run, so a sitemap-only store can take tens of seconds |
| `GET /api/v1/vendors/targets` | Now paginated: `?limit=&offset=&q=&review_state=draft\|approved&discovery_mode=auto\|selectors`. Adds `total`, `limit`, `offset`, `draft_count`; `count` is the page size. No `limit` = everything (unchanged for current callers) |
| `GET /api/v1/vendors/observations` | Already paginated (`limit`, `offset`, `total`); rows now also carry `variant_label`, `sku`, `extraction_method` |
| `GET /api/v1/vendors/observations/flagged` | Adds `offset` and `total` |

Target rows gain `store_url`, `discovery_mode`, `review_state`, `approved_at`, `approved_by`, `kind`.
`TargetPayload.selectors` may now be empty. `PUT` accepts `store_url`; a `PUT` that omits the field keeps the stored value (so the current admin drawer cannot wipe it).

## 5. Schema

Idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` statements at the end of the two migration files, applied
on startup while `VENDOR_SCHEMA_AUTO_CREATE=true`:

* `vendor_scrape_targets`: `store_url`, `review_state` (default `approved`), `approved_at`, `approved_by`,
  `kind` (default `competitor`).
* `vendor_price_observations`: `variant_label`, `sku`, `extraction_method`.

## 6. Limits

* Sites that render prices only in JavaScript and publish no JSON-LD/microdata/OpenGraph (some Next.js
  shops) still need selectors; the run says so in the observation instead of guessing.
* Shopify's `products.json` carries no currency; the target's `currency` is used (`null` otherwise).
* A WooCommerce variable product whose variations cannot be read keeps its "from" price as a flagged reading.
