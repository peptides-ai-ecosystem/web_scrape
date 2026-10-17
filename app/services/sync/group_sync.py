"""Group A and relation (C-F) sync steps of :class:`DbImportOrchestrator`.

A mixin split out of db_import_orchestrator.py to keep that file under 400
lines. It uses the mapper attributes the orchestrator sets in ``__init__``.
"""
from typing import Any, Dict, List, Optional

from app.core.logging import log_debug, log_error, log_info, log_success
from app.infrastructure.db import DbManager
from app.utils.error_tracker import ErrorTracker
from app.utils.peptide_utils import get_peptide_candidates, extract_essence, normalize_to_slug


class GroupSyncMixin:
    def _sync_group_a(self, db: DbManager, group_a: Dict[str, Any], tracker: Optional[ErrorTracker] = None, row_id: str = "") -> str:
        """Sync Group A lookup tables and return a short summary string.

        Each lookup type is isolated in its own try/except so a failure in one
        (e.g. a desynced id sequence) never blocks the remaining lookups.
        """
        counts = {"methods": 0, "benefits": 0, "side_effects": 0, "dosages": 0, "schedules": 0, "references": 0}

        def _record(label: str, e: Exception) -> None:
            if tracker:
                tracker.record_db_error(row_id or "?", f"group_a/{label}", e)
            log_error(f"  group_a/{label} sync failed: {e}", "db_import_orchestrator")

        try:
            for am in group_a["administration_methods"]:
                db.insert_lookup("administration_methods", am["name"], description=am.get("description"))
                counts["methods"] += 1
        except Exception as e:
            _record("administration_methods", e)

        try:
            for b in group_a["benefits"]:
                db.insert_lookup("benefits", b["name"], description=b.get("description"))
                counts["benefits"] += 1
        except Exception as e:
            _record("benefits", e)

        try:
            for se in group_a["side_effects"]:
                db.insert_lookup("side_effects", se["name"], description=se.get("description"))
                counts["side_effects"] += 1
        except Exception as e:
            _record("side_effects", e)

        try:
            for d in group_a["dosages"]:
                # Reconstruct full dose string (amount + unit) so _get_or_create_dosage_id
                # stores it with the correct unit, matching what upsert_protocol_dosage
                # looks up later (e.g. "1.75mg" not just "1.75").
                amount_str = d["amount"]
                unit = d.get("unit", "")
                full_str = f"{amount_str}{unit}" if unit else amount_str
                db._get_or_create_dosage_id(full_str)
                counts["dosages"] += 1
        except Exception as e:
            _record("dosages", e)

        try:
            for s in group_a["schedules"]:
                db.insert_lookup("schedules", s["name"], frequency=s.get("frequency"))
                counts["schedules"] += 1
        except Exception as e:
            _record("schedules", e)

        try:
            for st in group_a["studies"]:
                if st.get("type") == "study":
                    db.upsert_research_study(st)
                else:
                    db.upsert_citation(st)
                counts["references"] += 1
        except Exception as e:
            _record("studies", e)

        try:
            for place in group_a.get("application_places", []):
                db.insert_lookup("application_places", place)
        except Exception as e:
            _record("application_places", e)

        parts = [f"{v} {k}" for k, v in counts.items() if v]
        return ", ".join(parts) if parts else "nothing to sync"

    def _sync_relations(self, db: DbManager, peptide_id: int, relations: Dict[str, Any], protocols: List[Dict[str, Any]], tracker: Optional[ErrorTracker] = None, row_id: str = "", skip_kinds: Optional[set] = None) -> int:
        """Sync relations and return total count of records processed.

        Each relation sub-type is isolated in its own try/except so a failure
        in one (e.g. a lookup that can't be linked) never blocks the others —
        most importantly the research indications, references, and protocols.

        skip_kinds: relation kinds (benefits, side_effects, interactions,
        indications, references, protocols) left completely untouched — used
        by fill_empty_only for kinds the peptide already has.
        """
        count = 0
        skip_kinds = skip_kinds or set()

        def _safe(label: str, fn) -> None:
            nonlocal count
            if label in skip_kinds:
                return
            try:
                count += fn()
            except Exception as e:
                if tracker:
                    tracker.record_db_error(row_id or "?", f"relations/{label}", e)
                log_error(f"  relations/{label} sync failed: {e}", "db_import_orchestrator")

        # Link Benefits (Group C)
        def _link_benefits() -> int:
            n = 0
            for b in relations["benefits"]:
                b_id = db.get_lookup_id("benefits", b["benefit_name"])
                if b_id:
                    # db.link_relation is a generic helper that should handle (table, fk1, val1, fk2, val2)
                    db.link_relation("peptide_benefits", "peptide_id", peptide_id, "benefit_id", b_id)
                    n += 1
            return n
        _safe("benefits", _link_benefits)

        # Link Side Effects (Group C)
        def _link_side_effects() -> int:
            n = 0
            for se in relations["side_effects"]:
                se_id = db.get_lookup_id("side_effects", se["side_effect_name"])
                if se_id:
                    db.link_relation("peptide_side_effects", "peptide_id", peptide_id, "side_effect_id", se_id)
                    n += 1
            return n
        _safe("side_effects", _link_side_effects)

        # Link Interactions (Group C)
        def _link_interactions() -> int:
            n = 0
            for inter in relations["interactions"]:
                secondary_name = inter.get("secondary_peptide_name", "")
                if secondary_name:
                    matched = db.search_peptide_by_name(secondary_name)
                    if matched:
                        inter["secondary_peptide_id"] = matched["id"]
                        log_debug(
                            f"  Resolved interaction '{secondary_name}' → peptide_id={matched['id']}",
                            "db_import_orchestrator"
                        )
                db.upsert_interaction(peptide_id, inter)
                n += 1
            return n
        _safe("interactions", _link_interactions)

        # Link Indications (Group C/F)
        def _link_indications() -> int:
            n = 0
            for ind in relations["indications"]:
                db.upsert_indication(peptide_id, ind)
                n += 1
            return n
        _safe("indications", _link_indications)

        # Link Research Studies & Citations (Group C)
        def _link_references() -> int:
            n = 0
            for st in relations["references"]:
                ref_type = st.get("type", "study")
                if ref_type == "study":
                    ref_id = db.upsert_research_study(st)
                else:
                    ref_id = db.upsert_citation(st)
                db.upsert_peptide_reference(peptide_id, ref_type, ref_id)
                n += 1
            return n
        _safe("references", _link_references)

        # Handle Protocols (Groups D-F)
        def _link_protocols() -> int:
            n = 0
            for p in protocols:
                am_id = db.get_lookup_id("administration_methods", p["administration_method_name"])
                # Expectations are already JSON strings from the mapper
                protocol_id = db.upsert_protocol(peptide_id, am_id, p)

                # Sub-relations for protocol (Group E)
                for step in p["reconstitution_steps"]:
                    db.upsert_reconstitution_step(protocol_id, step)
                for ind in p["quality_indicators"]:
                    db.upsert_quality_indicator(protocol_id, ind)
                for place_name in p["application_places"]:
                    ap_id = db.get_lookup_id("application_places", place_name)
                    if ap_id:
                        db.link_relation("protocol_application_places", "protocol_id", protocol_id, "application_place_id", ap_id)
                for dose in p["dosages"]:
                    # Dose already has 'notes' formatted
                    db.upsert_protocol_dosage(protocol_id, dose)
                n += 1
            return n
        _safe("protocols", _link_protocols)

        return count
