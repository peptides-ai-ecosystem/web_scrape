# 0006 - The vendor products publisher is a raising seam

Status: accepted (2026-10-18).

## Context
Own-vendor prices reach the platform through the WooCommerce sync, which declared `vendor_products` single-writer. Competitor observations are stored here (`vendor_price_observations`) and the platform reads `observations/accepted-latest`. `app/scrapers/vendors/vendor_products_publisher.py` would push accepted readings into the platform's `vendor_products`, but that needs a platform endpoint that does not exist.

## Decision
`_send` raises `VendorProductsPublishUnavailable` by design. A run calls the publisher only to keep the seam visible, with `VENDOR_PRODUCTS_PUBLISH_ENABLED=false` (the default), and records the result under `vendor_products_publish`. No second writer is added to a platform table from here (XR-8). When the platform exposes the endpoint, implementing `_send` is an XR-14 change that lands after the platform's.

## Consequences
Status is "partial": observations and review work, publishing does not. Tracked as a follow-up issue, not as navigation in AGENTS.md.
