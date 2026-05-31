from typing import Any, Dict, List, Optional
from tqdm import tqdm
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
from src.mappers.group_d.graph_mapper import GraphMapper
from src.infrastructure.db_manager import DbManager
from src.utils.error_tracker import ErrorTracker

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
        self.graph_mapper = GraphMapper()

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
            "protocols": protocols,
            "graph_data": self.graph_mapper.map(row)
        }

    def sync_to_db(self, db_url: str, rows: List[Dict[str, Any]], tracker: Optional[ErrorTracker] = None):
        """
        Main entry point to sync rows using the grouped logic.
        """
        db = DbManager(db_url)
        try:
            for row in tqdm(rows, desc="Syncing to database", unit="row"):
                row_id = row.get("name") or row.get("peptide_name") or str(list(row.values())[:1])

                # Map raw row to payload
                try:
                    payload = self.map_row(row)
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "map_row", e)
                    continue

                # 1. Process Group A (Independent Lookups)
                try:
                    self._sync_group_a(db, payload["group_a"])
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "group_a", e)

                # 2. Process Group B (Peptides) — must succeed to continue
                try:
                    peptide_id = db.upsert_peptide_fill_nulls(payload["group_b"]["peptide"])
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "group_b", e)
                    continue

                # 3. Process Relations (Groups C-F)
                try:
                    self._sync_relations(db, peptide_id, payload["relations"], payload["protocols"], payload["graph_data"])
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "relations", e)
        finally:
            db.close()

    def _sync_group_a(self, db: DbManager, group_a: Dict[str, Any]):
        for am in group_a["administration_methods"]:
            db.insert_lookup("administration_methods", am["name"], description=am.get("description"))
        for b in group_a["benefits"]:
            db.insert_lookup("benefits", b["name"], description=b.get("description"))
        for se in group_a["side_effects"]:
            db.insert_lookup("side_effects", se["name"], description=se.get("description"))
        for d in group_a["dosages"]:
            # Uses amount_str to find/create dosage
            db._get_or_create_dosage_id(d["amount"])
        for s in group_a["schedules"]:
            db.insert_lookup("schedules", s["name"], frequency=s.get("frequency"))
        for st in group_a["studies"]:
            if st.get("type") == "study":
                db.upsert_research_study(st)
            else:
                db.upsert_citation(st)
        for place in group_a.get("application_places", []):
            db.insert_lookup("application_places", place)

    def _sync_relations(self, db: DbManager, peptide_id: int, relations: Dict[str, Any], protocols: List[Dict[str, Any]], graph_data: List[Dict[str, Any]]):
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
        
        # Link Graph Data (Group D)
        for gd in graph_data:
            method_name = gd.get("method", "Injectable")
            # Ensure the method name is normalized to match lookup table (Injectable, Oral, etc.)
            am_id = db.get_lookup_id("administration_methods", method_name)
            if am_id:
                db.upsert_graph_data(peptide_id, am_id, gd)
            else:
                # Fallback to 'Injectable' (ID 1) if lookup fails
                db.upsert_graph_data(peptide_id, 1, gd)
