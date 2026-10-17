"""Baseline: web_scrape's own competitor-scraping tables.

Revision ID: 4b1d0c2e9f10
Revises:
Create Date: 2026-10-17

Decision R10: the first revision only creates what is missing. Both tables
already exist on staging and production (they were created on every boot by
the old ``vendor_schema.py`` runner from ``migrations/*.sql``), so every
statement is ``IF NOT EXISTS``: on those databases this revision changes
nothing and only records itself in ``alembic_version_web_scrape``. On an empty
database it creates both tables with every column the code uses.

The SQL is the content of the two former files
``migrations/migration_vendor_price_observations.sql`` and
``migrations/migration_vendor_scrape_targets.sql``, unchanged.

Never alter a platform table here (XR-8).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "4b1d0c2e9f10"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VENDOR_PRICE_OBSERVATIONS_SQL = r"""
-- peptides-platform#288 — competitor vendor price observations.
--
-- This table lives in *this service's* database (DATABASE_URL), not in the
-- peptides-platform database that owns `vendor_products` (#263). See
-- src/services/vendor_products_publisher.py and
-- docs/features/05-vendor-scraping.md for why the scraper does not write to
-- `vendor_products` directly.
--
-- Nothing in here is a fact about a vendor's catalogue. Every row is one
-- *reading* of one page at one moment, carrying the confidence it was read
-- with and whether a human still owes it a review. Downstream readers must
-- filter on `review_status = 'accepted'`; reading this table unfiltered will
-- hand you prices we ourselves do not trust.

CREATE TABLE IF NOT EXISTS vendor_price_observations (
    id                    BIGSERIAL PRIMARY KEY,

    -- Vendor slug exactly as it appears in the targets config file.
    vendor                VARCHAR(64)   NOT NULL,
    url                   TEXT          NOT NULL,
    observed_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),

    -- ok | robots_disallowed | blocked | error | skipped
    status                VARCHAR(32)   NOT NULL DEFAULT 'ok',

    product_name          VARCHAR(512),

    -- NUMERIC, never float: this is money. NULL means "we could not read a
    -- price", and must never be rendered as 0 or as "free".
    price                 NUMERIC(12, 4),
    currency              VARCHAR(3),

    -- Mirrors the platform's vocabulary: instock | outofstock | onbackorder.
    -- NULL means the page did not tell us, not "in stock".
    stock_status          VARCHAR(32),

    coa_url               TEXT,

    -- 0..1, computed from which selectors actually matched — not from
    -- whether the run completed. See src/services/vendor_confidence.py.
    confidence            NUMERIC(4, 3) NOT NULL DEFAULT 0,
    confidence_breakdown  JSONB,

    -- accepted | flagged | rejected. A flagged row NEVER supersedes the last
    -- accepted row for the same (vendor, url).
    review_status         VARCHAR(16)   NOT NULL DEFAULT 'flagged',
    -- low_confidence | price_delta | no_price | currency_changed
    review_reason         VARCHAR(32),
    review_note           TEXT,
    reviewed_at           TIMESTAMPTZ,
    reviewed_by           VARCHAR(255),

    failure_detail        TEXT,

    created_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT vendor_price_observations_price_positive
        CHECK (price IS NULL OR price > 0),
    CONSTRAINT vendor_price_observations_confidence_range
        CHECK (confidence >= 0 AND confidence <= 1)
);

-- "What is the current accepted price for this listing?" — the hot path.
CREATE INDEX IF NOT EXISTS vendor_price_observations_current_idx
    ON vendor_price_observations (vendor, url, review_status, observed_at DESC);

-- Drives the admin review queue.
CREATE INDEX IF NOT EXISTS vendor_price_observations_review_idx
    ON vendor_price_observations (review_status, observed_at DESC);

CREATE INDEX IF NOT EXISTS vendor_price_observations_vendor_idx
    ON vendor_price_observations (vendor);

-- AAD-1: one reading per variant/size from selector-free discovery. The size
-- label is also in product_name (the platform import parses sizes from it);
-- these columns keep it, the SKU and how the reading was made, separately.
ALTER TABLE vendor_price_observations ADD COLUMN IF NOT EXISTS variant_label VARCHAR(255);
ALTER TABLE vendor_price_observations ADD COLUMN IF NOT EXISTS sku VARCHAR(255);
-- selectors | woo_store_api | shopify_json | json_ld | microdata | opengraph
ALTER TABLE vendor_price_observations ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(32);
"""

VENDOR_SCRAPE_TARGETS_SQL = r"""
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
"""


def upgrade() -> None:
    op.execute(VENDOR_PRICE_OBSERVATIONS_SQL)
    op.execute(VENDOR_SCRAPE_TARGETS_SQL)


def downgrade() -> None:
    # A baseline that adopts existing tables must not drop them (and their
    # data) on downgrade. Drop them by hand if that is really intended.
    pass
