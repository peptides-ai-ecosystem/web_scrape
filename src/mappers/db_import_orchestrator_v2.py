"""
DbImportOrchestratorV2 — Optimized sync orchestrator.

THE critical fix: one transaction per peptide row.

v1 behaviour (slow):
  Every single SQL statement called _commit() immediately.
  For a typical peptide row that fires ~30 statements, this meant
  ~30 TCP round-trips to Supabase just for commits (~50–200ms each).

v2 behaviour (fast):
  1. db.begin()         ← opens the transaction
  2. All ~30 statements run inside the same transaction (no network flush)
  3. db.commit()        ← ONE round-trip per row
  On error → db.rollback() — the row is skipped cleanly.

All other query-level optimisations (ON CONFLICT, no SELECT-before-INSERT,
no SELECT 1 ping) are implemented in the individual v2 repositories.

Usage (replaces sync_to_db call in main.py):
    from src.mappers.db_import_orchestrator_v2 import DbImportOrchestratorV2
    orchestrator = DbImportOrchestratorV2()
    orchestrator.sync_to_db(os.getenv("DATABASE_URL"), rows, tracker=tracker)
"""
from typing import Any, Dict, List, Optional
from tqdm import tqdm

from src.mappers.group_a.lookup_mappers import (
    AdministrationMethodMapper,
    BenefitMapper,
    SideEffectMapper,
    DosageMapper,
    ScheduleMapper,
    ResearchStudyMapper,
)
from src.mappers.group_b.peptide_mapper import PeptideMapper
from src.mappers.group_c.relation_mappers import RelationMapper
from src.mappers.group_d.protocol_mapper import ProtocolMapper
from src.mappers.group_d.graph_mapper import GraphMapper
from src.infrastructure.db_v2 import DbManagerV2
from src.utils.error_tracker import ErrorTracker


class DbImportOrchestratorV2:
    """
    Converts raw CSV rows into structured payloads and syncs them to the DB.

    Identical mapper pipeline to v1; only the DB interaction layer differs.
    """

    def __init__(self):
        self.admin_method_mapper = AdministrationMethodMapper()
        self.benefit_mapper      = BenefitMapper()
        self.side_effect_mapper  = SideEffectMapper()
        self.dosage_mapper       = DosageMapper()
        self.schedule_mapper     = ScheduleMapper()
        self.study_mapper        = ResearchStudyMapper()
        self.peptide_mapper      = PeptideMapper()
        self.relation_mapper     = RelationMapper()
        self.protocol_mapper     = ProtocolMapper()
        self.graph_mapper        = GraphMapper()

    # ------------------------------------------------------------------
    # Mapping (unchanged from v1)
    # ------------------------------------------------------------------

    def map_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        protocols  = self.protocol_mapper.map(row)
        app_places = list({place for p in protocols for place in p["application_places"]})
        return {
            "group_a": {
                "administration_methods": self.admin_method_mapper.map(row),
                "benefits":              self.benefit_mapper.map(row),
                "side_effects":          self.side_effect_mapper.map(row),
                "dosages":               self.dosage_mapper.map(row),
                "schedules":             self.schedule_mapper.map(row),
                "studies":               self.study_mapper.map(row),
                "application_places":    app_places,
            },
            "group_b":   {"peptide": self.peptide_mapper.map(row)},
            "relations":  self.relation_mapper.map(row),
            "protocols":  protocols,
            "graph_data": self.graph_mapper.map(row),
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def sync_to_db(
        self,
        db_url: str,
        rows: List[Dict[str, Any]],
        tracker: Optional[ErrorTracker] = None,
    ):
        """
        Sync all rows to the database.

        Each row is wrapped in its own transaction:
          - If the row succeeds  → commit (1 round-trip)
          - If any step fails    → rollback, record error, continue
        """
        db = DbManagerV2(db_url)
        try:
            for row in tqdm(rows, desc="Syncing to database (v2)", unit="row"):
                row_id = (
                    row.get("name")
                    or row.get("peptide_name")
                    or str(list(row.values())[:1])
                )

                # ── Map raw CSV row ─────────────────────────────────
                try:
                    payload = self.map_row(row)
                except Exception as e:
                    if tracker:
                        tracker.record_db_error(row_id, "map_row", e)
                    continue

                # ── Single transaction per row ───────────────────────
                try:
                    db.begin()

                    # 1. Group A — independent lookups
                    self._sync_group_a(db, payload["group_a"])

                    # 2. Group B — peptide (must succeed to continue)
                    peptide_id = db.upsert_peptide_fill_nulls(payload["group_b"]["peptide"])

                    # 3. Relations / protocols / graph
                    self._sync_relations(
                        db, peptide_id,
                        payload["relations"],
                        payload["protocols"],
                        payload["graph_data"],
                    )

                    # ✅ ONE commit for the entire row
                    db.commit()

                except Exception as e:
                    db.rollback()
                    if tracker:
                        tracker.record_db_error(row_id, "sync_row", e)

        finally:
            db.close()

    # ------------------------------------------------------------------
    # Group sync helpers (same logic as v1, no commits inside)
    # ------------------------------------------------------------------

    def _sync_group_a(self, db: DbManagerV2, group_a: Dict[str, Any]):
        for am in group_a["administration_methods"]:
            db.insert_lookup("administration_methods", am["name"],
                             description=am.get("description"))
        for b in group_a["benefits"]:
            db.insert_lookup("benefits", b["name"], description=b.get("description"))
        for se in group_a["side_effects"]:
            db.insert_lookup("side_effects", se["name"], description=se.get("description"))
        for d in group_a["dosages"]:
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

    def _sync_relations(
        self,
        db: DbManagerV2,
        peptide_id: int,
        relations: Dict[str, Any],
        protocols: List[Dict[str, Any]],
        graph_data: List[Dict[str, Any]],
    ):
        # Benefits (Group C)
        for b in relations["benefits"]:
            b_id = db.get_lookup_id("benefits", b["benefit_name"])
            if b_id:
                db.link_relation("peptide_benefits", "peptide_id", peptide_id, "benefit_id", b_id)

        # Side Effects (Group C)
        for se in relations["side_effects"]:
            se_id = db.get_lookup_id("side_effects", se["side_effect_name"])
            if se_id:
                db.link_relation("peptide_side_effects", "peptide_id", peptide_id, "side_effect_id", se_id)

        # Interactions (Group C)
        for inter in relations["interactions"]:
            db.upsert_interaction(peptide_id, inter)

        # Indications (Groups C/F)
        for ind in relations["indications"]:
            db.upsert_indication(peptide_id, ind)

        # Research Studies & Citations (Group C)
        for st in relations["references"]:
            ref_type = st.get("type", "study")
            ref_id   = db.upsert_research_study(st) if ref_type == "study" else db.upsert_citation(st)
            db.upsert_peptide_reference(peptide_id, ref_type, ref_id)

        # Protocols (Groups D-F)
        for p in protocols:
            am_id = db.get_lookup_id("administration_methods", p["administration_method_name"])
            protocol_id = db.upsert_protocol(peptide_id, am_id, p)

            for step in p["reconstitution_steps"]:
                db.upsert_reconstitution_step(protocol_id, step)
            for ind in p["quality_indicators"]:
                db.upsert_quality_indicator(protocol_id, ind)
            for place_name in p["application_places"]:
                ap_id = db.get_lookup_id("application_places", place_name)
                if ap_id:
                    db.link_relation("protocol_application_places", "protocol_id", protocol_id, "application_place_id", ap_id)
            for dose in p["dosages"]:
                db.upsert_protocol_dosage(protocol_id, dose)

        # Graph Data (Group D)
        for gd in graph_data:
            method_name = gd.get("method", "Injectable")
            am_id = db.get_lookup_id("administration_methods", method_name)
            db.upsert_graph_data(peptide_id, am_id if am_id else 1, gd)
