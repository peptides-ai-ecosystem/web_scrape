"""Competitor price observations (``/api/v1/vendors/observations*``).

Reads and the human review of flagged readings, over
``vendor_price_observations`` (this service's own table).
"""
from typing import Any, Dict, Optional

from src.core.errors import ConflictError, InvalidInputError, NotFoundError
from src.core.vendor_models import ReviewStatus, ScrapeStatus
from src.infrastructure.db.connection import DbConnection
from src.infrastructure.db.repositories import VendorObservationRepository
from src.services.vendor_scrape_runner import all_targets
from src.services.vendor_target_service import db_url

_REVIEW_VALUES = {s.value for s in ReviewStatus}
_STATUS_VALUES = {s.value for s in ScrapeStatus}


def _repository() -> VendorObservationRepository:
    return VendorObservationRepository(DbConnection(db_url()))


def list_observations(
    vendor: Optional[str], review_status: Optional[str], status: Optional[str], limit: int, offset: int
) -> Dict[str, Any]:
    """Every reading, newest first, filtered by vendor / review status / scrape status."""
    if review_status and review_status not in _REVIEW_VALUES:
        raise InvalidInputError(f"review_status must be one of {sorted(_REVIEW_VALUES)}")
    if status and status not in _STATUS_VALUES:
        raise InvalidInputError(f"status must be one of {sorted(_STATUS_VALUES)}")
    repo = _repository()
    try:
        page = repo.list_observations(
            vendor=vendor, review_status=review_status, status=status, limit=limit, offset=offset
        )
    finally:
        repo.connection.close()
    return {
        "total": page["total"],
        "limit": limit,
        "offset": offset,
        "observations": page["rows"],
    }


def list_flagged(limit: int, vendor: Optional[str], offset: int) -> Dict[str, Any]:
    """The review queue: readings not trusted enough to replace an accepted value."""
    repo = _repository()
    try:
        rows = repo.list_flagged(limit=limit, vendor=vendor, offset=offset)
        total = repo.count_flagged(vendor=vendor)
    finally:
        repo.connection.close()
    return {
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "vendor": vendor,
        "observations": rows,
    }


def list_latest_accepted(vendor: Optional[str]) -> Dict[str, Any]:
    """The newest accepted reading per ``(vendor, url)`` with its target's names attached."""
    repo = _repository()
    try:
        rows = repo.list_latest_accepted(vendor=vendor)
    finally:
        repo.connection.close()
    mapping = {t.slug.lower(): t for t in all_targets(include_disabled=True)}
    for row in rows:
        target = mapping.get(str(row.get("vendor") or "").lower())
        row["vendor_name"] = target.name if target else None
        row["platform_vendor_slug"] = (
            (target.platform_vendor_slug or target.slug) if target else row.get("vendor")
        )
    return {"count": len(rows), "vendor": vendor, "observations": rows}


def review(observation_id: int, decision: str, reviewer: Optional[str]) -> Dict[str, Any]:
    """Accept or reject one flagged reading; 404 unknown, 409 already resolved or no price."""
    repo = _repository()
    try:
        status = ReviewStatus.ACCEPTED if decision == "accept" else ReviewStatus.REJECTED
        updated = repo.resolve_review(observation_id, status, reviewer)
        if not updated:
            row = repo.get_row(observation_id)
            if row is None:
                raise NotFoundError(f"No observation {observation_id}.")
            if row.get("review_status") != ReviewStatus.FLAGGED.value:
                raise ConflictError(f"Observation {observation_id} is already {row.get('review_status')}.")
            raise ConflictError(f"Observation {observation_id} has no price and can only be rejected.")
    finally:
        repo.connection.close()
    return {"observation_id": observation_id, "review_status": status.value, "updated": updated}
