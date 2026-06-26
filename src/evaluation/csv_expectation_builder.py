"""
CsvExpectationBuilder
=====================
Reuses the existing mapper stack (DbImportOrchestrator) to derive the
*expected* database state from a raw CSV row, with no new parsing logic.
"""
import re
from typing import Any, Dict, Optional

from src.mappers.db_import_orchestrator import DbImportOrchestrator
from src.mappers.group_d.graph_mapper import GraphMapper


# Mirror of the METHOD_KEYWORD_MAP defined in DbImportOrchestrator.sync_to_db
METHOD_KEYWORD_MAP = {
    "nasal": "Nasal Spray",
    "intranasal": "Nasal Spray",
    "topical": "Topical Cream",
    "oral": "Capsule",
    "injectable": "Injectable",
}


class CsvExpectationBuilder:
    """
    Converts a raw CSV row into the expected DB payload by running the
    same mappers used during the actual sync.

    Returns None if the row would have been *skipped* by the orchestrator
    (e.g. unmappable administration method), so the caller can skip the
    evaluation for that peptide as well.
    """

    def __init__(self):
        self._orchestrator = DbImportOrchestrator()
        self._graph_mapper = GraphMapper()

    def resolve_method(self, row: Dict[str, Any]) -> Optional[str]:
        """Return the canonical DB method name or None if unmappable."""
        raw_method = str(row.get("Method") or "").strip()
        first_part = raw_method.split(",")[0].strip().lower()
        for keyword, method_name in METHOD_KEYWORD_MAP.items():
            if keyword in first_part:
                return method_name
        return None

    def build(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Build the expected payload from a CSV row.

        Returns a dict with keys:
            - peptide_name   : str
            - slug           : str
            - administration_method : str | None  (mapped canonical name)
            - peptide        : dict  (group_b fields)
            - administration_methods : list[dict]
            - benefits       : list[dict]
            - side_effects   : list[dict]
            - dosages        : list[dict]
            - schedules      : list[dict]
            - references     : list[dict]
            - interactions   : list[dict]
            - indications    : list[dict]
            - protocols      : list[dict]
            - graph_data     : list[dict]

        Returns None if the row would be skipped by the orchestrator.
        """
        raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()
        slug = re.sub(r"[^a-z0-9]+", "-", raw_name.lower()).strip("-")

        # Resolve administration method (same logic as orchestrator)
        mapped_method = self.resolve_method(row)
        if not mapped_method:
            return None  # orchestrator would skip — nothing to evaluate

        # Overwrite Method so mappers see the canonical name (mirrors sync)
        patched_row = dict(row)
        patched_row["Method"] = mapped_method

        # Run full mapper stack
        payload = self._orchestrator.map_row(patched_row)
        ga = payload["group_a"]
        relations = payload["relations"]

        # Graph data is handled separately (GraphImportOrchestrator) — call
        # the mapper directly so the expected payload includes it for evaluation.
        graph_data = self._graph_mapper.map(patched_row)

        return {
            "peptide_name": raw_name,
            "slug": slug,
            "administration_method": mapped_method,
            # group_b
            "peptide": payload["group_b"]["peptide"],
            # group_a lookups
            "administration_methods": ga["administration_methods"],
            "benefits": ga["benefits"],
            "side_effects": ga["side_effects"],
            "dosages": ga["dosages"],
            "schedules": ga["schedules"],
            "references": ga["studies"],
            # group_c relations
            "interactions": relations["interactions"],
            "indications": relations["indications"],
            # groups d-f
            "protocols": payload["protocols"],
            "graph_data": graph_data,
        }
