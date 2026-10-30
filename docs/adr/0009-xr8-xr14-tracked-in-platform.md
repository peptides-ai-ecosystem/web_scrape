# 0009 XR-8 and XR-14 follow-ups are tracked in the platform

Status: Accepted (2026-10-18)

Both open cross-repo items need a change in peptides-platform first, so they are tracked there:

- [XR-8] four undeclared `peptides` columns (`molecular_type`, `molecular_length`, `molecular_weight`,
  `activity_type`): https://github.com/peptides-apps/peptides-platform/issues/522. Done for the columns by platform
  Drizzle migration 0138 (webscrape-1, 30 Oct 2026): `KNOWN_UNDECLARED_COLUMNS` is empty and the hand-run `migrations/` folder
  is deleted (ADR 0003, ADR 0007).
- [XR-14] the vendor products publisher seam, which stays a raising stub until the platform exposes an endpoint:
  https://github.com/peptides-apps/peptides-platform/issues/523 (ADR 0006).

Enforced in: `tests/sync/test_platform_schema_contract.py`, `app/scrapers/vendors/vendor_products_publisher.py`.
