-- CEO feedback round 2 (P2) — competitor scrape targets managed from the admin
-- "Pepti.AI -> Scrape" tab instead of only a JSON file.
--
-- Lives in *this service's* database (DATABASE_URL), next to
-- vendor_price_observations. The file named by VENDOR_TARGETS_FILE remains a
-- seed / fallback: a file target is used only while no row here has the same
-- slug (see src/infrastructure/vendor_targets.merge_targets).
--
-- Idempotent: safe to re-run, and applied automatically on startup when
-- VENDOR_SCHEMA_AUTO_CREATE=true (the default).

CREATE TABLE IF NOT EXISTS vendor_scrape_targets (
    id                            BIGSERIAL PRIMARY KEY,

    -- Stable identifier; also the `vendor` column of vendor_price_observations.
    slug                          VARCHAR(64)   NOT NULL,
    name                          VARCHAR(255)  NOT NULL,
    enabled                       BOOLEAN       NOT NULL DEFAULT TRUE,

    -- JSON array of absolute http(s) product page URLs.
    product_urls                  JSONB         NOT NULL DEFAULT '[]'::jsonb,
    -- Optional category page; product links are discovered from it with
    -- listing_link_selector (same host only).
    listing_url                   TEXT,
    listing_link_selector         TEXT,

    -- {"price": [...], "stock": [...], "coa": [...], "product_name": [...]}
    -- ordered CSS selector candidates, primary first.
    selectors                     JSONB         NOT NULL DEFAULT '{}'::jsonb,

    -- ISO-4217 fallback when the page shows no currency symbol.
    currency                      VARCHAR(3),

    -- Politeness: seconds between requests to this host (never below the
    -- global VENDOR_SCRAPE_MIN_INTERVAL_SECONDS floor or robots Crawl-delay).
    min_request_interval_seconds  NUMERIC(8, 2) NOT NULL DEFAULT 5.0,
    max_products_per_run          INTEGER,

    -- platform `vendors.slug` the prices are imported onto (NULL = slug).
    platform_vendor_slug          VARCHAR(255),

    created_at                    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at                    TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT vendor_scrape_targets_slug_not_empty CHECK (length(trim(slug)) > 0),
    CONSTRAINT vendor_scrape_targets_interval_non_negative
        CHECK (min_request_interval_seconds >= 0),
    CONSTRAINT vendor_scrape_targets_max_products_positive
        CHECK (max_products_per_run IS NULL OR max_products_per_run >= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS vendor_scrape_targets_slug_uidx
    ON vendor_scrape_targets (lower(slug));

-- AAD-1 (CEO final feedback): scrape a competitor from a URL only.
--   store_url     a store's home, shop or product URL; with no price selector
--                 the target is read through the WooCommerce Store API, Shopify
--                 products.json or sitemaps + schema.org JSON-LD.
--   review_state  'draft' targets (created from a bare URL) are listed and can
--                 be previewed but are never scraped until an admin approves
--                 them; existing rows were configured by an admin -> approved.
--   kind          always 'competitor': our own stores are refused as targets.
ALTER TABLE vendor_scrape_targets ADD COLUMN IF NOT EXISTS store_url TEXT;
ALTER TABLE vendor_scrape_targets
    ADD COLUMN IF NOT EXISTS review_state VARCHAR(16) NOT NULL DEFAULT 'approved';
ALTER TABLE vendor_scrape_targets ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;
ALTER TABLE vendor_scrape_targets ADD COLUMN IF NOT EXISTS approved_by VARCHAR(255);
ALTER TABLE vendor_scrape_targets
    ADD COLUMN IF NOT EXISTS kind VARCHAR(16) NOT NULL DEFAULT 'competitor';
