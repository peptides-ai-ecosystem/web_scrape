from typing import Any, Dict, List, Optional
import re
from src.mappers.group_a.lookup_mappers import (
    AdministrationMethodMapper,
    BenefitMapper,
    SideEffectMapper,
    DosageMapper,
    ScheduleMapper,
    ResearchStudyMapper
)
from src.mappers.group_b.peptide_mapper import PeptideMapper
from src.mappers.group_c.relation_mappers import RelationMapper
from src.mappers.group_d.protocol_mapper import ProtocolMapper
from src.infrastructure.db import DbManager
from src.utils.error_tracker import ErrorTracker
from src.utils.peptide_utils import get_peptide_candidates, extract_essence, normalize_to_slug
from src.config import log_debug, log_error

class DbImportOrchestrator:
    """
    Orchestrates the conversion of a raw data row into structured payloads by group.
    """

    def __init__(self):
        # Group A
        self.admin_method_mapper = AdministrationMethodMapper()
        self.benefit_mapper = BenefitMapper()
        self.side_effect_mapper = SideEffectMapper()
        self.dosage_mapper = DosageMapper()
        self.schedule_mapper = ScheduleMapper()
        self.study_mapper = ResearchStudyMapper()
        
        # Group B
        self.peptide_mapper = PeptideMapper()
        
        # Groups C-F
        self.relation_mapper = RelationMapper()
        self.protocol_mapper = ProtocolMapper()

    def map_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps a single row into a grouped payload structure.
        """
        protocols = self.protocol_mapper.map(row)
        app_places = list({place for p in protocols for place in p["application_places"]})
        
        return {
            "group_a": {
                "administration_methods": self.admin_method_mapper.map(row),
                "benefits": self.benefit_mapper.map(row),
                "side_effects": self.side_effect_mapper.map(row),
                "dosages": self.dosage_mapper.map(row),
                "schedules": self.schedule_mapper.map(row),
                "studies": self.study_mapper.map(row),
                "application_places": app_places
            },
            "group_b": {
                "peptide": self.peptide_mapper.map(row)
            },
            "relations": self.relation_mapper.map(row),
            "protocols": protocols
        }

    def sync_to_db(self, db_url: str, rows: List[Dict[str, Any]], tracker: Optional[ErrorTracker] = None):
        """
        Main entry point to sync rows using the grouped logic.
        Only processes peptides that already exist in the database.
        """
        db = DbManager(db_url)
        try:
            log_debug(f"Starting database sync for {len(rows)} rows", "db_import_orchestrator")
            # Pre-fetch all existing peptide identifiers and their essences
            db_identifiers = db.get_all_peptide_identifiers()
            db_essences = {extract_essence(ident): ident for ident in db_identifiers}
            print(f"[INFO] Found {len(db_identifiers)} peptides in DB, {len(db_essences)} unique essences")

            # Pre-fetch all existing administration methods from DB
            db_admin_methods = db.get_all_administration_methods()
            existing_method_names = {m["name"] for m in db_admin_methods}
            print(f"[INFO] Found {len(existing_method_names)} administration methods in DB: {existing_method_names}")

            # Keyword-to-DB-name mapping rules
            METHOD_KEYWORD_MAP = {
                "nasal": "Nasal Spray",
                "intranasal": "Nasal Spray",
                "topical": "Topical Cream",
                "oral": "Capsule",
                "injectable": "Injectable",
            }

            skipped_count = 0
            total = len(rows)
            synced_count = 0
            for idx, row in enumerate(rows, start=1):
                row_id = row.get("name") or row.get("peptide_name") or str(list(row.values())[:1])

                # Extract peptide name from CSV row and generate candidate slugs
                raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()
                candidates = get_peptide_candidates(raw_name)
                # Sort longest-first to prefer more specific slugs (e.g.
                # "hexarelin-examorelin" over "hexarelin") and avoid false
                # matches when a shorter slug belongs to a different peptide.
                sorted_candidates = sorted(candidates, key=len, reverse=True)
                
                # Match candidates against DB identifiers or essences
                matched_identifier = None
                for cand in sorted_candidates:
                    if cand in db_identifiers:
                        matched_identifier = cand
                        break
                    if cand in db_essences:
                        matched_identifier = db_essences[cand]
                        break

                # Skip if this peptide doesn't exist in DB
                if not matched_identifier:
                    skipped_count += 1
                    log_debug(f"Skipped: {raw_name} - no match found in Peptides table (candidates: {candidates})", "db_import_orchestrator")
                    continue

                # Use the matched identifier for slug-based lookups
                row_slug = matched_identifier

                # Stage 0.5: Map Administrative Method and filter
                raw_method = str(row.get("Method") or "").strip()
                # If multiple methods, only take the first one
                first_method_part = raw_method.split(",")[0].strip().lower()
                
                # Resolve CSV keyword to a DB method name
                mapped_method = None
                for keyword, method_name in METHOD_KEYWORD_MAP.items():
                    if keyword in first_method_part:
                        mapped_method = method_name
                        break
                
                # Skip if keyword didn't match or mapped method doesn't exist in DB
                if not mapped_method or mapped_method not in existing_method_names:
                    skipped_count += 1
                    if mapped_method and mapped_method not in existing_method_names:
                        log_debug(f"Skipped: {raw_name} - mapped method '{mapped_method}' does not exist in administrative method table", "db_import_orchestrator")
                    else:
                        log_debug(f"Skipped: {raw_name} - administrative method '{raw_method}' has no mapping", "db_import_orchestrator")
                    continue
                
                # Overwrite the row's method so downstream mappers use the DB method name
                row["Method"] = mapped_method

                print(f"\n{raw_name} : {mapped_method}")
                log_debug(f"Processing peptide: {raw_name} with method: {mapped_method}", "db_import_orchestrator")

                # Stage 1: Map raw row to payload
                print(f"  Stage 1: Mapping raw row to structured payload")
                try:
                    payload = self.map_row(row)
                    ga = payload["group_a"]
                    s1_summary = (
                        f"{len(ga['dosages'])} dosages, "
                        f"{len(ga['benefits'])} benefits, "
                        f"{len(ga['side_effects'])} side effects, "
                        f"{len(ga['schedules'])} schedules, "
                        f"{len(ga['studies'])} references"
                    )
                    print(f"         → mapped: {s1_summary}")
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "map_row", e)
                    print(f"  ✗ Stage 1 failed: {e}")
                    continue

                # Stage 2: Sync Group A lookup tables
                print(f"  Stage 2: Syncing lookup tables (dosages, benefits, side effects, schedules)")
                try:
                    a_summary = self._sync_group_a(db, payload["group_a"])
                    print(f"         → {a_summary}")
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "group_a", e)

                # Stage 3: Upsert peptide record — check before to detect insert vs update
                print(f"  Stage 3: Upserting peptide record")
                try:
                    peptide_slug = payload["group_b"]["peptide"].get("slug")
                    pre_existing = db.get_peptide_by_slug(peptide_slug)
                    peptide_id = db.upsert_peptide_fill_nulls(payload["group_b"]["peptide"])
                    if not pre_existing:
                        print(f"         → inserted new peptide record")
                    else:
                        # Count how many fields were null before and now have values
                        pep_payload = payload["group_b"]["peptide"]
                        filled = sum(
                            1 for col, val in pep_payload.items()
                            if val and (pre_existing.get(col) is None or pre_existing.get(col) == "")
                        )
                        if filled:
                            print(f"         → updated {filled} previously empty field(s)")
                        else:
                            print(f"         → already complete, no changes")
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "group_b", e)
                    print(f"  ✗ Stage 3 failed: {e}")
                    continue

                # Stage 4: Link relations, protocols
                print(f"  Stage 4: Linking relations and protocols")
                try:
                    r_count = self._sync_relations(db, peptide_id, payload["relations"], payload["protocols"])
                    print(f"         → {r_count} relation record(s) processed")
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "relations", e)

                synced_count += 1
                print(f"  ✓ Done")

            if skipped_count > 0:
                print(f"[INFO] Skipped {skipped_count} peptide(s) not found in DB")
                log_debug(f"Skipped {skipped_count} peptides during sync", "db_import_orchestrator")
            print(f"[INFO] Synced {synced_count} peptide(s) successfully")
            log_debug(f"Successfully synced {synced_count} peptides", "db_import_orchestrator")
        finally:
            db.close()

    def _sync_group_a(self, db: DbManager, group_a: Dict[str, Any]) -> str:
        """Sync Group A lookup tables and return a short summary string."""
        counts = {"methods": 0, "benefits": 0, "side_effects": 0, "dosages": 0, "schedules": 0, "references": 0}
        for am in group_a["administration_methods"]:
            db.insert_lookup("administration_methods", am["name"], description=am.get("description"))
            counts["methods"] += 1
        for b in group_a["benefits"]:
            db.insert_lookup("benefits", b["name"], description=b.get("description"))
            counts["benefits"] += 1
        for se in group_a["side_effects"]:
            db.insert_lookup("side_effects", se["name"], description=se.get("description"))
            counts["side_effects"] += 1
        for d in group_a["dosages"]:
            db._get_or_create_dosage_id(d["amount"])
            counts["dosages"] += 1
        for s in group_a["schedules"]:
            db.insert_lookup("schedules", s["name"], frequency=s.get("frequency"))
            counts["schedules"] += 1
        for st in group_a["studies"]:
            if st.get("type") == "study":
                db.upsert_research_study(st)
            else:
                db.upsert_citation(st)
            counts["references"] += 1
        for place in group_a.get("application_places", []):
            db.insert_lookup("application_places", place)
        parts = [f"{v} {k}" for k, v in counts.items() if v]
        return ", ".join(parts) if parts else "nothing to sync"

    def _sync_relations(self, db: DbManager, peptide_id: int, relations: Dict[str, Any], protocols: List[Dict[str, Any]]) -> int:
        """Sync relations and return total count of records processed."""
        # Link Benefits (Group C)
        for b in relations["benefits"]:
            b_id = db.get_lookup_id("benefits", b["benefit_name"])
            if b_id:
                # db.link_relation is a generic helper that should handle (table, fk1, val1, fk2, val2)
                db.link_relation("peptide_benefits", "peptide_id", peptide_id, "benefit_id", b_id)

        # Link Side Effects (Group C)
        for se in relations["side_effects"]:
            se_id = db.get_lookup_id("side_effects", se["side_effect_name"])
            if se_id:
                db.link_relation("peptide_side_effects", "peptide_id", peptide_id, "side_effect_id", se_id)

        # Link Interactions (Group C)
        for inter in relations["interactions"]:
            db.upsert_interaction(peptide_id, inter)

        # Link Indications (Group C/F)
        for ind in relations["indications"]:
            db.upsert_indication(peptide_id, ind)

        # Link Research Studies & Citations (Group C)
        for st in relations["references"]:
            ref_type = st.get("type", "study")
            if ref_type == "study":
                ref_id = db.upsert_research_study(st)
            else:
                ref_id = db.upsert_citation(st)
            db.upsert_peptide_reference(peptide_id, ref_type, ref_id)

        # Handle Protocols (Groups D-F)
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
