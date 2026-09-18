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
