"""Pharmacokinetics graph reads (``/api/v1/peptides``, ``/pk/peptides``, ``/graph/{id}``).

Each call checks a connection out of the shared pool and reads through
``GraphRepository``. Errors that map to a 4xx are raised as typed service
errors; anything else propagates and the endpoint answers 500.
"""
from typing import Any, Dict, List

from app.core.errors import InvalidInputError, NotFoundError
from app.infrastructure.db.pool import get_pool


def list_peptides_with_graph() -> List[Dict[str, Any]]:
    """Peptides that have at least one ``peptide_graph`` row, sorted by name."""
    with get_pool().acquire() as db:
        return db.graph.list_peptides_with_graph()


def list_pk_summary() -> Dict[str, Any]:
    """Every peptide with PK curves, for the admin PK tab: ``{count, peptides}``."""
    with get_pool().acquire() as db:
        peptides = db.graph.list_pk_summary()
    return {"count": len(peptides), "peptides": peptides}


def methods_for_peptide(peptide_id: int) -> List[Dict[str, Any]]:
    """Administration methods with graph data for one peptide; 404 when there are none."""
    with get_pool().acquire() as db:
        methods = db.graph.get_methods_for_peptide(peptide_id)
    if not methods:
        raise NotFoundError(
            f"No graph data found for peptide ID {peptide_id}. "
            "Check GET /api/v1/peptides for valid peptide IDs."
        )
    return methods


def graph_data(peptide_id: int, method: str) -> Dict[str, Any]:
    """Graph data keyed by time range for one peptide + administration method.

    An empty or unknown ``method`` is rejected (422) instead of silently
    falling back to the repository's default "Injectable".
    """
    with get_pool().acquire() as db:
        methods = db.graph.get_methods_for_peptide(peptide_id)
        if not methods:
            raise NotFoundError(
                f"Peptide {peptide_id} not found or has no graph data. "
                "Check GET /api/v1/peptides for valid peptide IDs."
            )

        method = (method or "").strip()
        valid = [m["name"] for m in methods]
        matched = next((m for m in valid if m.lower() == method.lower()), None)
        if not matched:
            raise InvalidInputError(
                f"Invalid method '{method}' for peptide {peptide_id}. "
                f"Valid methods: {', '.join(valid)}"
            )

        data = db.graph.get_visualization_data(peptide_id, matched)
    if not data or not any(
        k not in ["peptide_name", "administration_method"] for k in data.keys()
    ):
        raise NotFoundError(f"No graph data found for peptide {peptide_id} with method '{matched}'")
    return data
