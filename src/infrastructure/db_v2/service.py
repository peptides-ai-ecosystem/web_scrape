"""
DbServiceV2 — Facade wiring all v2 repositories.

DbManagerV2 is the drop-in replacement for the legacy DbManager,
exposing the exact same method names so callers can be updated by
just changing the import.
"""
from typing import Any, Dict, List, Optional
from src.infrastructure.db_v2.connection import DbConnectionV2
from src.infrastructure.db_v2.repositories import (
    LookupRepositoryV2,
    PeptideRepositoryV2,
    ResearchStudyRepositoryV2,
    CitationRepositoryV2,
    ReferenceRepositoryV2,
    InteractionRepositoryV2,
    IndicationRepositoryV2,
    ProtocolRepositoryV2,
    DosageRepositoryV2,
    GraphRepositoryV2,
)


class DbServiceV2:
    """
    Facade that wires all v2 repositories to a single connection.
    All repositories share the same connection, so a single
    conn.commit() covers every write made through this service.
    """

    def __init__(self, connection):
        self.connection = connection
        self.lookup      = LookupRepositoryV2(connection)
        self.peptide     = PeptideRepositoryV2(connection)
        self.research_study = ResearchStudyRepositoryV2(connection)
        self.citation    = CitationRepositoryV2(connection)
        self.reference   = ReferenceRepositoryV2(connection)
        self.interaction = InteractionRepositoryV2(connection)
        self.indication  = IndicationRepositoryV2(connection)
        self.protocol    = ProtocolRepositoryV2(connection)
        self.dosage      = DosageRepositoryV2(connection)
        self.graph       = GraphRepositoryV2(connection)


class DbManagerV2:
    """
    Drop-in replacement for the legacy DbManager.
    Method signatures are identical — swap the import to use v2.

    Critical difference: no commit is issued inside any method.
    The orchestrator is responsible for calling conn.commit() once
    per peptide row, reducing Supabase round-trips by ~30×.
    """

    def __init__(self, db_url: str):
        self.db_connection = DbConnectionV2(db_url)
        self.service = DbServiceV2(self.db_connection)

    # ------------------------------------------------------------------
    # Transaction control (called by the orchestrator)
    # ------------------------------------------------------------------

    def begin(self):
        self.db_connection.begin()

    def commit(self):
        self.db_connection.commit()

    def rollback(self):
        self.db_connection.rollback()

    def close(self):
        self.db_connection.close()

    # ------------------------------------------------------------------
    # Delegating methods — identical signatures to legacy DbManager
    # ------------------------------------------------------------------

    def insert_lookup(self, table: str, name: str, **kwargs) -> int:
        return self.service.lookup.upsert(table, name, **kwargs)

    def get_lookup_id(self, table: str, name: str) -> Optional[int]:
        return self.service.lookup.get_id_by_name(table, name)

    def upsert_research_study(self, study: Dict[str, Any]) -> int:
        return self.service.research_study.upsert(study)

    def upsert_citation(self, citation: Dict[str, Any]) -> int:
        return self.service.citation.upsert(citation)

    def get_research_study_id(self, title: str) -> Optional[int]:
        return self.service.research_study.get_id_by_title(title)

    def get_citation_id(self, title: str) -> Optional[int]:
        return self.service.citation.get_id_by_title(title)

    def upsert_peptide_fill_nulls(self, payload: Dict[str, Any]) -> int:
        return self.service.peptide.upsert_fill_nulls(payload)

    def upsert_peptide_reference(self, peptide_id: int, ref_type: str, ref_id: int):
        self.service.reference.upsert_peptide_reference(peptide_id, ref_type, ref_id)

    def upsert_interaction(self, peptide_id: int, interaction: Dict[str, Any]):
        self.service.interaction.upsert(peptide_id, interaction)

    def upsert_indication(self, peptide_id: int, indication: Dict[str, Any]):
        self.service.indication.upsert(peptide_id, indication)

    def upsert_protocol(self, peptide_id: int, am_id: int, protocol: Dict[str, Any]) -> int:
        return self.service.protocol.upsert(peptide_id, am_id, protocol)

    def upsert_reconstitution_step(self, protocol_id: int, step: Dict[str, Any]):
        self.service.protocol.upsert_reconstitution_step(protocol_id, step)

    def upsert_quality_indicator(self, protocol_id: int, indicator: Dict[str, Any]):
        self.service.protocol.upsert_quality_indicator(protocol_id, indicator)

    def upsert_protocol_dosage(self, protocol_id: int, dosage: Dict[str, Any]):
        self.service.dosage.upsert_protocol_dosage(protocol_id, dosage)

    def _get_or_create_dosage_id(self, amount_str: str, create: bool = True) -> Optional[int]:
        return self.service.dosage.get_or_create_dosage_id(amount_str, create)

    def upsert_graph_data(self, peptide_id: int, am_id: int, graph_data: Dict[str, Any]):
        self.service.graph.upsert(peptide_id, am_id, graph_data)

    def get_methods_for_peptide(self, peptide_id: int) -> List[Dict[str, Any]]:
        return self.service.graph.get_methods_for_peptide(peptide_id)

    def link_relation(self, table: str, fk1_col: str, fk1_val: int,
                      fk2_col: str, fk2_val: int):
        self.service.reference.link_entities(table, fk1_col, fk1_val, fk2_col, fk2_val)
