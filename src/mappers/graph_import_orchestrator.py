from typing import Any, Dict, List, Optional
from src.mappers.group_d.graph_mapper import GraphMapper
from src.infrastructure.db import DbManager
from src.utils.error_tracker import ErrorTracker
from src.utils.peptide_utils import get_peptide_candidates, extract_essence
from src.config import log_debug, log_error

class GraphImportOrchestrator:
    """
    Orchestrates the conversion of a raw data row into structured graph payloads.
    Dedicated purely to syncing graph data separately from table parameters.
    """
    def __init__(self):
        self.graph_mapper = GraphMapper()

    def sync_graph_data(self, db_url: str, rows: List[Dict[str, Any]], tracker: Optional[ErrorTracker] = None):
        """
        Main entry point to sync graph logic separately based on raw CSV data.
        Only processes graph data for peptides that already exist in the database.
        """
        db = DbManager(db_url)
        try:
            log_debug(f"Starting database sync for {len(rows)} graph rows", "graph_import_orchestrator")
            db_identifiers = db.get_all_peptide_identifiers()
            db_essences = {extract_essence(ident): ident for ident in db_identifiers}
            
            skipped_count = 0
            synced_count = 0
            
            for idx, row in enumerate(rows, start=1):
                raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()
                row_id = raw_name or str(list(row.values())[:1])
                candidates = get_peptide_candidates(raw_name)
                
                matched_identifier = None
                for cand in candidates:
                    if cand in db_identifiers:
                        matched_identifier = cand
                        break
                    if cand in db_essences:
                        matched_identifier = db_essences[cand]
                        break

                if not matched_identifier:
                    skipped_count += 1
                    continue
                
                # Fetch DB peptide record by slug
                peptide_record = db.get_peptide_by_slug(matched_identifier)
                if not peptide_record:
                    skipped_count += 1
                    continue
                
                peptide_id = peptide_record["id"]
                
                # Retrieve Graph map
                try:
                    graph_data = self.graph_mapper.map(row)
                    for gd in graph_data:
                        method_name = gd.get("method", "Injectable")
                        am_id = db.get_lookup_id("administration_methods", method_name)
                        if am_id:
                            db.upsert_graph_data(peptide_id, am_id, gd)
                        else:
                            db.upsert_graph_data(peptide_id, 1, gd) # fallback to Injectable
                    synced_count += 1
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "graph_sync", e)
                    continue
                    
        finally:
            db.close()
            
        print(f"[INFO] Graph Sync complete. Synced: {synced_count}, Skipped: {skipped_count}")

    def sync_graph_missing_data(self, db_url: str, rows: List[Dict[str, Any]], tracker: Optional[ErrorTracker] = None):
        """
        Syncs graph data only if it is missing for the given peptide and administration method.
        """
        db = DbManager(db_url)
        try:
            log_debug(f"Starting missing database sync for {len(rows)} graph rows", "graph_import_orchestrator")
            db_identifiers = db.get_all_peptide_identifiers()
            db_essences = {extract_essence(ident): ident for ident in db_identifiers}
            
            skipped_count = 0
            synced_count = 0
            
            for idx, row in enumerate(rows, start=1):
                raw_name = (row.get("Peptide_Name") or row.get("name") or "").strip()
                row_id = raw_name or str(list(row.values())[:1])
                candidates = get_peptide_candidates(raw_name)
                
                matched_identifier = None
                for cand in candidates:
                    if cand in db_identifiers:
                        matched_identifier = cand
                        break
                    if cand in db_essences:
                        matched_identifier = db_essences[cand]
                        break

                if not matched_identifier:
                    skipped_count += 1
                    continue
                
                # Fetch DB peptide record by slug
                peptide_record = db.get_peptide_by_slug(matched_identifier)
                if not peptide_record:
                    skipped_count += 1
                    continue
                
                peptide_id = peptide_record["id"]
                
                # Fetch existing methods for this peptide
                existing_methods = db.get_methods_for_peptide(peptide_id)
                existing_am_ids = {m["id"] for m in existing_methods}
                
                # Retrieve Graph map
                try:
                    graph_data = self.graph_mapper.map(row)
                    has_synced = False
                    for gd in graph_data:
                        method_name = gd.get("method", "Injectable")
                        am_id = db.get_lookup_id("administration_methods", method_name)
                        if not am_id:
                            am_id = 1 # fallback to Injectable
                            
                        # Only insert if this exact am_id is missing for this peptide
                        if am_id not in existing_am_ids:
                            db.upsert_graph_data(peptide_id, am_id, gd)
                            has_synced = True
                            
                    if has_synced:
                        synced_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "graph_sync_missing", e)
                    continue
                    
        finally:
            db.close()
            
        print(f"[INFO] Graph Sync Missing complete. Synced rows: {synced_count}, Skipped rows: {skipped_count}")
