"""Core Data Inspector reads (``/api/v1/core/*``): what the sync wrote into the platform tables."""
from typing import Any, Dict, List, Optional

from app.core.errors import NotFoundError
from app.infrastructure.db.pool import get_pool


def list_peptides(q: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every peptide in the core database, optionally filtered by a name/slug substring."""
    with get_pool().acquire() as db:
        return db.inspector.list_peptides(q)


def peptide_by_id(peptide_id: int) -> Dict[str, Any]:
    """The full inspector payload for one peptide id; 404 when it does not exist."""
    with get_pool().acquire() as db:
        peptide = db.peptide.get_by_id(peptide_id)
        if not peptide:
            raise NotFoundError(f"Peptide ID {peptide_id} not found")
        return db.inspector.fetch_payload(dict(peptide))


def peptide_by_slug(slug: str) -> Dict[str, Any]:
    """The full inspector payload for one peptide slug; 404 when it does not exist."""
    with get_pool().acquire() as db:
        peptide = db.peptide.get_by_slug(slug)
        if not peptide:
            raise NotFoundError(f"Peptide slug '{slug}' not found")
        return db.inspector.fetch_payload(dict(peptide))


def lookups() -> Dict[str, List[Dict[str, Any]]]:
    """Every lookup catalog in one round-trip."""
    with get_pool().acquire() as db:
        return db.inspector.lookups()
