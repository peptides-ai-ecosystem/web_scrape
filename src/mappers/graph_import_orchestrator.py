from typing import Any, Dict, List, Optional
from src.mappers.group_d.graph_mapper import GraphMapper
from src.infrastructure.db import DbManager
from src.utils.error_tracker import ErrorTracker
from src.utils.peptide_utils import get_peptide_candidates, extract_essence
from src.config import log_debug, log_error, log_info, log_success

class GraphImportOrchestrator:
    """
    Orchestrates the conversion of a raw data row into structured graph payloads.
    Dedicated purely to syncing graph data separately from table parameters.
    """

    # Keyword-to-DB-name mapping for administration methods.
    # Scraped website values differ from canonical DB names (e.g. "Nasal" → "Nasal Spray").
    METHOD_KEYWORD_MAP = {
        "nasal": "Nasal Spray",
        "intranasal": "Nasal Spray",
        "topical": "Topical Cream",
        "oral": "Capsule",
        "injectable": "Injectable",
    }

    def __init__(self):
        self.graph_mapper = GraphMapper()

    @staticmethod
    def _normalize_method(method_name: str) -> str:
        """Map a scraped keyword to the canonical DB administration method name."""
        return GraphImportOrchestrator.METHOD_KEYWORD_MAP.get(method_name.strip().lower(), method_name.strip())

    def sync_graph_data(self, db_url: str, rows: List[Dict[str, Any]], tracker: Optional[ErrorTracker] = None, action_type: str = 'manual'):
        """
        Main entry point to sync graph logic separately based on raw CSV data.
        Only processes graph data for peptides that already exist in the database.
        """
        db = DbManager(db_url)
        try:
            log_info(f"GRAPH SYNC STARTED — {len(rows)} row(s) to inject", "graph_import_orchestrator")
            db_identifiers = db.get_all_peptide_identifiers()
            log_debug(f"Found {len(db_identifiers)} existing peptide identifiers in DB", "graph_import_orchestrator")
            db_essences = {extract_essence(ident): ident for ident in db_identifiers}
            
            skipped_count = 0
            synced_count = 0
            skipped_peptides = []
            synced_peptides = []
            
            for idx, row in enumerate(rows, start=1):
                raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()
                row_id = raw_name or str(list(row.values())[:1])
                candidates = get_peptide_candidates(raw_name)
                # Sort longest-first to prefer more specific slugs (e.g.
                # "hexarelin-examorelin" over "hexarelin") and avoid false
                # matches when a shorter slug belongs to a different peptide.
                sorted_candidates = sorted(candidates, key=len, reverse=True)
                
                log_debug(f"[{idx}/{len(rows)}] Processing: '{raw_name}' - candidates: {sorted_candidates}", "graph_import_orchestrator")
                
                matched_identifier = None
                for cand in sorted_candidates:
                    if cand in db_identifiers:
                        matched_identifier = cand
                        log_debug(f"  Match found: '{raw_name}' → DB slug '{cand}' (direct match)", "graph_import_orchestrator")
                        break
                    if cand in db_essences:
                        matched_identifier = db_essences[cand]
                        log_debug(f"  Match found: '{raw_name}' → DB slug '{db_essences[cand]}' (via essence '{cand}')", "graph_import_orchestrator")
                        break

                if not matched_identifier:
                    skipped_count += 1
                    skipped_peptides.append(raw_name)
                    log_debug(f"  ✗ SKIPPED: '{raw_name}' - no matching peptide found in database. Generated candidates: {sorted_candidates}", "graph_import_orchestrator")
                    continue
                
                # Fetch DB peptide record by slug
                peptide_record = db.get_peptide_by_slug(matched_identifier)
                if not peptide_record:
                    skipped_count += 1
                    skipped_peptides.append(raw_name)
                    log_debug(f"  ✗ SKIPPED: '{raw_name}' - slug '{matched_identifier}' resolved but not found in peptides table", "graph_import_orchestrator")
                    continue
                
                peptide_id = peptide_record["id"]
                log_debug(f"  ✓ MATCHED: '{raw_name}' → peptide_id={peptide_id}, slug='{matched_identifier}'", "graph_import_orchestrator")
                
                # Retrieve Graph map
                try:
                    graph_data = self.graph_mapper.map(row)
                    if not graph_data:
                        log_debug(f"  ⚠ SKIPPED: '{raw_name}' - graph_mapper.map() returned no graph data (no graph_data_json in CSV)", "graph_import_orchestrator")
                        skipped_count += 1
                        skipped_peptides.append(raw_name)
                        continue
                    
                    injected_methods = []
                    for gd in graph_data:
                        raw_method = gd.get("method", "Injectable")
                        method_name = self._normalize_method(raw_method)
                        time_range = gd.get("time_range", "N/A")
                        am_id = db.get_lookup_id("administration_methods", method_name)
                        if am_id:
                            db.upsert_graph_data(peptide_id, am_id, gd, action_type)
                            log_debug(f"    → Injected: '{raw_name}' | method='{method_name}' (am_id={am_id}) | time_range='{time_range}'", "graph_import_orchestrator")
                        else:
                            db.upsert_graph_data(peptide_id, 1, gd, action_type) # fallback to Injectable
                            log_debug(f"    → Injected: '{raw_name}' | method='Injectable' (fallback, am_id=1) | time_range='{time_range}'", "graph_import_orchestrator")
                        injected_methods.append(method_name)
                    
                    synced_count += 1
                    synced_peptides.append({"name": raw_name, "slug": matched_identifier, "methods": list(set(injected_methods))})
                    log_success(f"Graph sync — '{raw_name}' methods: {list(set(injected_methods))}", "graph_import_orchestrator")
                    
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "graph_sync", e)
                    log_error(f"Graph sync — '{raw_name}' failed: {e}", "graph_import_orchestrator")
                    continue
                    
        finally:
            db.close()
        
        # Summary section
        summary_lines = [
            f"\n{'='*60}",
            f"  GRAPH SYNC SUMMARY",
            f"{'='*60}",
            f"  Total rows processed: {len(rows)}",
            f"  ✅ Synced: {synced_count}",
            f"  ❌ Skipped: {skipped_count}",
        ]
        if synced_peptides:
            summary_lines.append(f"\n  --- Synced Peptides ---")
            for p in synced_peptides:
                summary_lines.append(f"  ✅ {p['name']} (slug: {p['slug']}) → methods: {p['methods']}")
        if skipped_peptides:
            summary_lines.append(f"\n  --- Skipped Peptides ---")
            for name in skipped_peptides:
                summary_lines.append(f"  ❌ {name}")
        summary_lines.append(f"{'='*60}\n")
        
        summary = "\n".join(summary_lines)
        print(summary)
        log_debug(summary, "graph_import_orchestrator")
        
        # Also log separately for easy reading
        for p in synced_peptides:
            log_success(f"Graph sync — {p['name']} (slug: {p['slug']}, methods: {p['methods']})", "graph_import_orchestrator")
        for name in skipped_peptides:
            log_debug(f"Skipped — {name}", "graph_import_orchestrator")

        log_info(f"GRAPH SYNC COMPLETED — {synced_count} synced, {skipped_count} skipped", "graph_import_orchestrator")
        
        # Return summary for API job result enrichment
        return {
            "synced_count": synced_count,
            "skipped_count": skipped_count,
            "synced_peptides": synced_peptides,
            "skipped_peptides": skipped_peptides,
        }

    def sync_graph_missing_data(self, db_url: str, rows: List[Dict[str, Any]], tracker: Optional[ErrorTracker] = None, action_type: str = 'manual'):
        """
        Syncs graph data only if it is missing for the given peptide and administration method.
        """
        db = DbManager(db_url)
        try:
            log_info(f"GRAPH MISSING SYNC STARTED — {len(rows)} row(s) to check", "graph_import_orchestrator")
            db_identifiers = db.get_all_peptide_identifiers()
            log_debug(f"Found {len(db_identifiers)} existing peptide identifiers in DB", "graph_import_orchestrator")
            db_essences = {extract_essence(ident): ident for ident in db_identifiers}
            
            skipped_count = 0
            synced_count = 0
            skipped_peptides = []
            synced_peptides = []
            
            for idx, row in enumerate(rows, start=1):
                raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()
                row_id = raw_name or str(list(row.values())[:1])
                candidates = get_peptide_candidates(raw_name)
                sorted_candidates = sorted(candidates, key=len, reverse=True)
                
                log_debug(f"[{idx}/{len(rows)}] Processing: '{raw_name}' - candidates: {sorted_candidates}", "graph_import_orchestrator")
                
                matched_identifier = None
                for cand in sorted_candidates:
                    if cand in db_identifiers:
                        matched_identifier = cand
                        log_debug(f"  Match found: '{raw_name}' → DB slug '{cand}' (direct match)", "graph_import_orchestrator")
                        break
                    if cand in db_essences:
                        matched_identifier = db_essences[cand]
                        log_debug(f"  Match found: '{raw_name}' → DB slug '{db_essences[cand]}' (via essence '{cand}')", "graph_import_orchestrator")
                        break

                if not matched_identifier:
                    skipped_count += 1
                    skipped_peptides.append(raw_name)
                    log_debug(f"  ✗ SKIPPED: '{raw_name}' - no matching peptide found in database. Candidates: {sorted_candidates}", "graph_import_orchestrator")
                    continue
                
                # Fetch DB peptide record by slug
                peptide_record = db.get_peptide_by_slug(matched_identifier)
                if not peptide_record:
                    skipped_count += 1
                    skipped_peptides.append(raw_name)
                    log_debug(f"  ✗ SKIPPED: '{raw_name}' - slug '{matched_identifier}' not found in peptides table", "graph_import_orchestrator")
                    continue
                
                peptide_id = peptide_record["id"]
                
                # Fetch existing methods for this peptide
                existing_methods = db.get_methods_for_peptide(peptide_id)
                existing_am_ids = {m["id"] for m in existing_methods}
                log_debug(f"  ✓ MATCHED: '{raw_name}' → peptide_id={peptide_id} | existing methods: {existing_am_ids}", "graph_import_orchestrator")
                
                # Retrieve Graph map
                try:
                    graph_data = self.graph_mapper.map(row)
                    if not graph_data:
                        log_debug(f"  ⚠ SKIPPED: '{raw_name}' - graph_mapper.map() returned no graph data", "graph_import_orchestrator")
                        skipped_count += 1
                        skipped_peptides.append(raw_name)
                        continue
                    
                    has_synced = False
                    injected_methods = []
                    for gd in graph_data:
                        raw_method = gd.get("method", "Injectable")
                        method_name = self._normalize_method(raw_method)
                        time_range = gd.get("time_range", "N/A")
                        am_id = db.get_lookup_id("administration_methods", method_name)
                        if not am_id:
                            am_id = 1 # fallback to Injectable
                            
                        if am_id not in existing_am_ids:
                            db.upsert_graph_data(peptide_id, am_id, gd, action_type)
                            log_debug(f"    → Injected (missing): '{raw_name}' | method='{method_name}' (am_id={am_id}) | time_range='{time_range}'", "graph_import_orchestrator")
                            has_synced = True
                            injected_methods.append(method_name)
                        else:
                            log_debug(f"    → Skipped (exists): '{raw_name}' | method='{method_name}' (am_id={am_id}) already has data", "graph_import_orchestrator")
                            
                    if has_synced:
                        synced_count += 1
                        synced_peptides.append({"name": raw_name, "slug": matched_identifier, "methods": list(set(injected_methods))})
                        log_debug(f"  ✓ SYNCED: '{raw_name}' - injected missing methods: {list(set(injected_methods))}", "graph_import_orchestrator")
                    else:
                        skipped_count += 1
                        skipped_peptides.append(f"{raw_name} (all methods already exist)")
                        log_debug(f"  – SKIPPED: '{raw_name}' - all methods already have graph data", "graph_import_orchestrator")
                        
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "graph_sync_missing", e)
                    log_debug(f"  ✗ ERROR: '{raw_name}' - failed to map/inject graph data: {e}", "graph_import_orchestrator")
                    continue
        
        finally:
            db.close()
        
        # Summary section
        summary_lines = [
            f"\n{'='*60}",
            f"  GRAPH SYNC MISSING SUMMARY",
            f"{'='*60}",
            f"  Total rows processed: {len(rows)}",
            f"  ✅ Synced (new methods injected): {synced_count}",
            f"  ❌ Skipped: {skipped_count}",
        ]
        if synced_peptides:
            summary_lines.append(f"\n  --- Synced Peptides (new methods injected) ---")
            for p in synced_peptides:
                summary_lines.append(f"  ✅ {p['name']} (slug: {p['slug']}) → new methods: {p['methods']}")
        if skipped_peptides:
            summary_lines.append(f"\n  --- Skipped Peptides ---")
            for name in skipped_peptides:
                summary_lines.append(f"  ❌ {name}")
        summary_lines.append(f"{'='*60}\n")
        
        summary = "\n".join(summary_lines)
        print(summary)
        log_debug(summary, "graph_import_orchestrator")
        
        for p in synced_peptides:
            log_success(f"Graph missing sync — {p['name']} (slug: {p['slug']}, new methods: {p['methods']})", "graph_import_orchestrator")
        for name in skipped_peptides:
            log_debug(f"Skipped — {name}", "graph_import_orchestrator")

        log_info(f"GRAPH MISSING SYNC COMPLETED — {synced_count} injected, {skipped_count} skipped", "graph_import_orchestrator")
        
        return {
            "synced_count": synced_count,
            "skipped_count": skipped_count,
            "synced_peptides": synced_peptides,
            "skipped_peptides": skipped_peptides,
        }
