# 0001 - One service, one package per scraper, the common service layout

Status: accepted (code review of 17 October 2026, MS-7).

## Context
The repo used `src/`, kept request models in endpoint files, had no controllers or tests folders by theme, and applied SQL by hand. A second site to scrape would have meant a copy of the repo.

## Decision
- One FastAPI service with the layout the other microservices use: `main.py` -> `app/factory.py`, `app/api/v1/endpoints/`, `app/controllers/`, `app/services/`, `app/repositories/`, `app/models/` (Pydantic), `app/core/` (settings, errors, scheduler), `app/infrastructure/`.
- Each scraper is a package under `app/scrapers/` (`pep_pedia/`, `vendors/`) registered in `app/scrapers/registry.py`. A new site is a new package in this service, not a new repository.
- Request and response shapes that cross HTTP are Pydantic (`app/models/`); internal rows stay dataclasses (`app/core/models.py`, `app/core/vendor_models.py`).
- Tests live in `tests/<theme>/` with a marker and a README per theme. Files stay under 400 lines.

## Consequences
Route paths, JSON keys and the OpenAPI path list stay identical (XR-14). Moves are done by copying and updating callers, one commit per step. Mixins split two long classes (`TargetResolutionMixin`, `GroupSyncMixin`) rather than rewriting them.
