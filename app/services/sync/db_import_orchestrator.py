from typing import Any, Dict, List, Optional
import re
from app.services.sync.group_a.lookup_mappers import (
    AdministrationMethodMapper,
    BenefitMapper,
    SideEffectMapper,
    DosageMapper,
    ScheduleMapper,
    ResearchStudyMapper
)
from app.services.sync.group_b.peptide_mapper import PeptideMapper
from app.services.sync.group_c.relation_mappers import RelationMapper
from app.services.sync.group_d.protocol_mapper import ProtocolMapper
from app.infrastructure.db import DbManager
from app.services.sync.group_sync import GroupSyncMixin
from app.utils.error_tracker import ErrorTracker
from app.utils.peptide_utils import get_peptide_candidates, extract_essence, normalize_to_slug
from app.core.logging import log_debug, log_error, log_info, log_success

class DbImportOrchestrator(GroupSyncMixin):
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

    def sync_to_db(self, db_url: str, rows: List[Dict[str, Any]], tracker: Optional[ErrorTracker] = None, activity_type: Optional[str] = None, fill_empty_only: bool = False) -> Dict[str, Any]:
        """
        Main entry point to sync rows using the grouped logic.
        Only processes peptides that already exist in the database.

        Args:
            db_url: Database connection URL.
            rows: List of raw data rows to sync.
            tracker: Optional error tracker.
            activity_type: If set (e.g. 'manual'), marks each synced peptide's
                           activity_type after upsert. When called from an API
                           endpoint, pass 'manual' so the peptide is flagged as
                           endpoint-triggered. When called from other paths
                           (e.g. direct CSV import), leave None so it stays NULL.
            fill_empty_only: Used after a curator approves a new peptide. The
                           matched peptide row is never inserted or overwritten;
                           only its empty columns are filled. Child rows
                           (benefits, side effects, interactions, indications,
                           references, protocols with their dosages) are added
                           only for kinds the peptide has none of yet, and
                           activity_type is stamped only when it is empty.
        """
        db = DbManager(db_url)
        try:
            log_info(f"CORE SYNC STARTED — {len(rows)} row(s) to process", "db_import_orchestrator")
            # Pre-fetch all existing peptide identifiers and their essences
            db_identifiers = db.get_all_peptide_identifiers()
            db_essences = {extract_essence(ident): ident for ident in db_identifiers}
            log_info(f"Found {len(db_identifiers)} peptides in DB, {len(db_essences)} unique essences", "db_import_orchestrator")

            # Pre-fetch all existing administration methods from DB
            db_admin_methods = db.get_all_administration_methods()
            existing_method_names = {m["name"] for m in db_admin_methods}
            log_info(f"Found {len(existing_method_names)} administration methods in DB: {existing_method_names}", "db_import_orchestrator")

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
            skipped_peptides = []
            synced_peptides = []

            for idx, row in enumerate(rows, start=1):
                row_id = row.get("name") or row.get("peptide_name") or str(list(row.values())[:1])

                # Extract peptide name from CSV row and generate candidate slugs
                raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()
                candidates = get_peptide_candidates(raw_name)
                # Sort longest-first to prefer more specific slugs (e.g.
                # "hexarelin-examorelin" over "hexarelin") and avoid false
                # matches when a shorter slug belongs to a different peptide.
                sorted_candidates = sorted(candidates, key=len, reverse=True)

                log_debug(f"[{idx}/{len(rows)}] Processing: '{raw_name}' - candidates: {sorted_candidates}", "db_import_orchestrator")

                # Match candidates against DB identifiers or essences
                matched_identifier = None
                for cand in sorted_candidates:
                    if cand in db_identifiers:
                        matched_identifier = cand
                        log_debug(f"  Match found: '{raw_name}' → DB slug '{cand}' (direct match)", "db_import_orchestrator")
                        break
                    if cand in db_essences:
                        matched_identifier = db_essences[cand]
                        log_debug(f"  Match found: '{raw_name}' → DB slug '{db_essences[cand]}' (via essence '{cand}')", "db_import_orchestrator")
                        break

                # Skip if this peptide doesn't exist in DB
                if not matched_identifier:
                    skipped_count += 1
                    skipped_peptides.append(f"{raw_name} (no DB match)")
                    log_debug(f"  ✗ SKIPPED: '{raw_name}' - no match found in Peptides table (candidates: {candidates})", "db_import_orchestrator")
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
                        reason = f"mapped method '{mapped_method}' not in DB"
                        log_debug(f"  ✗ SKIPPED: '{raw_name}' - mapped method '{mapped_method}' does not exist in administrative method table", "db_import_orchestrator")
                    else:
                        reason = f"admin method '{raw_method}' has no mapping"
                        log_debug(f"  ✗ SKIPPED: '{raw_name}' - administrative method '{raw_method}' has no mapping", "db_import_orchestrator")
                    skipped_peptides.append(f"{raw_name} ({reason})")
                    continue

                # Overwrite the row's method so downstream mappers use the DB method name
                row["Method"] = mapped_method

                print(f"\n{raw_name} : {mapped_method}")
                log_debug(f"  ✓ MATCHED: '{raw_name}' → method='{mapped_method}', slug='{row_slug}'", "db_import_orchestrator")

                # Fill-empty mode: resolve the existing row up front so a slug
                # mismatch can never insert a second peptide, and record which
                # child kinds already exist so they are left untouched.
                existing_row = None
                kinds_present: Dict[str, bool] = {}
                if fill_empty_only:
                    existing_row = db.get_peptide_by_identifier(row_slug)
                    if not existing_row:
                        skipped_count += 1
                        skipped_peptides.append(f"{raw_name} (fill_empty_only: no peptide row for '{row_slug}')")
                        continue
                    kinds_present = db.get_child_kinds_present(existing_row["id"])

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
                    skipped_count += 1
                    skipped_peptides.append(f"{raw_name} (Stage 1 mapping failed: {e})")
                    log_debug(f"  ✗ SKIPPED: '{raw_name}' - Stage 1 mapping failed: {e}", "db_import_orchestrator")
                    continue

                # Stage 2: Sync Group A lookup tables
                print(f"  Stage 2: Syncing lookup tables (dosages, benefits, side effects, schedules)")
                try:
                    a_summary = self._sync_group_a(db, payload["group_a"], tracker=tracker, row_id=str(row_id))
                    print(f"         → {a_summary}")
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "group_a", e)

                # Stage 3: Upsert peptide record — check before to detect insert vs update
                print(f"  Stage 3: Upserting peptide record")
                try:
                    if fill_empty_only:
                        # Never insert, never overwrite: fill empty columns only.
                        peptide_id = existing_row["id"]
                        filled_cols = db.fill_empty_peptide_columns(peptide_id, payload["group_b"]["peptide"])
                        print(f"         → fill_empty_only: filled {len(filled_cols)} empty field(s)")
                    else:
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
                    skipped_count += 1
                    skipped_peptides.append(f"{raw_name} (Stage 3 upsert failed: {e})")
                    log_debug(f"  ✗ SKIPPED: '{raw_name}' - Stage 3 upsert failed: {e}", "db_import_orchestrator")
                    continue

                # Stage 4: Link relations, protocols
                print(f"  Stage 4: Linking relations and protocols")
                try:
                    skip_kinds = {k for k, present in kinds_present.items() if present}
                    if skip_kinds:
                        print(f"         → fill_empty_only: keeping existing {', '.join(sorted(skip_kinds))}")
                    r_count = self._sync_relations(db, peptide_id, payload["relations"], payload["protocols"], tracker=tracker, row_id=str(row_id), skip_kinds=skip_kinds)
                    print(f"         → {r_count} relation record(s) processed")
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "relations", e)

                synced_count += 1
                synced_peptides.append({"name": raw_name, "slug": row_slug, "method": mapped_method})
                # Mark as endpoint-triggered if activity_type is provided
                if activity_type and peptide_id:
                    if not fill_empty_only or not existing_row.get("activity_type"):
                        db.update_peptide_activity_type(peptide_id, activity_type)
                print(f"  ✓ SYNCED: '{raw_name}' (slug: {row_slug})")
                log_success(f"Core sync — '{raw_name}' (slug: {row_slug}, method: {mapped_method})", "db_import_orchestrator")

            # Summary section
            summary_lines = [
                f"\n{'='*60}",
                f"  CORE DB SYNC SUMMARY",
                f"{'='*60}",
                f"  Total rows processed: {len(rows)}",
                f"  ✅ Synced: {synced_count}",
                f"  ❌ Skipped: {skipped_count}",
            ]
            if synced_peptides:
                summary_lines.append(f"\n  --- Synced Peptides ---")
                for p in synced_peptides:
                    summary_lines.append(f"  ✅ {p['name']} (slug: {p['slug']}) → method: {p['method']}")
            if skipped_peptides:
                summary_lines.append(f"\n  --- Skipped Peptides ---")
                for name in skipped_peptides:
                    summary_lines.append(f"  ❌ {name}")
            summary_lines.append(f"{'='*60}\n")

            summary = "\n".join(summary_lines)
            print(summary)
            log_debug(summary, "db_import_orchestrator")

            for p in synced_peptides:
                log_success(f"Core sync — {p['name']} (slug: {p['slug']}, method: {p['method']})", "db_import_orchestrator")
            for name in skipped_peptides:
                log_debug(f"Skipped — {name}", "db_import_orchestrator")

            log_info(f"CORE SYNC COMPLETED — {synced_count} synced, {skipped_count} skipped", "db_import_orchestrator")

            return {
                "synced_count": synced_count,
                "skipped_count": skipped_count,
                "synced_peptides": synced_peptides,
                "skipped_peptides": skipped_peptides,
            }

        finally:
            db.close()
