"""Database service facade for backward compatibility and orchestration."""
from typing import Dict, Any, Optional, List
from src.infrastructure.db.connection import DbConnection, DbPool
from src.infrastructure.db.repositories import (
    PeptideRepository,
    ProtocolRepository,
    ResearchStudyRepository,
    CitationRepository,
    InteractionRepository,
    IndicationRepository,
    GraphRepository,
    DosageRepository,
    ReferenceRepository,
    LookupRepository,
)


class DbService:
    """
    Facade service that coordinates all repositories.
    
    Provides a simpler interface similar to the original DbManager,
    while using the new repository pattern internally.
    
    Usage:
        service = DbService(db_connection)
        
        # Use any repository through the service
        peptide_id = service.peptide.upsert_fill_nulls(payload)
        protocol_id = service.protocol.upsert(peptide_id, am_id, protocol_data)
        study_id = service.research_study.upsert(study_data)
    """

    def __init__(self, connection):
        """
        Initialize service with a database connection.
        
        Args:
            connection: DbConnection, DbPool, or raw psycopg2 connection
        """
        self.connection = connection
        
        # Initialize repositories
        self.peptide = PeptideRepository(connection)
        self.protocol = ProtocolRepository(connection)
        self.research_study = ResearchStudyRepository(connection)
        self.citation = CitationRepository(connection)
        self.interaction = InteractionRepository(connection)
        self.indication = IndicationRepository(connection)
        self.graph = GraphRepository(connection)
        self.dosage = DosageRepository(connection)
        self.reference = ReferenceRepository(connection)
        self.lookup = LookupRepository(connection)

    # ==================== High-level orchestration methods ====================
    
    def upsert_peptide_with_data(self, peptide_payload: Dict[str, Any], 
                                  references: List[Dict[str, Any]] = None) -> int:
        """
        Upserts a peptide and optionally links it to studies/citations.
        
        Args:
            peptide_payload: Peptide data
            references: List of {'type': 'study'|'citation', 'id': ref_id}
        
        Returns:
            Peptide ID
        """
        peptide_id = self.peptide.upsert_fill_nulls(peptide_payload)
        
        if references:
            for ref in references:
                self.reference.upsert_peptide_reference(
                    peptide_id, 
                    ref.get('type'), 
                    ref.get('id')
                )
        
        return peptide_id

    def upsert_protocol_with_details(self, peptide_id: int, am_id: int,
                                     protocol_data: Dict[str, Any],
                                     dosages: List[Dict[str, Any]] = None,
                                     reconstitution_steps: List[Dict[str, Any]] = None,
                                     quality_indicators: List[Dict[str, Any]] = None) -> int:
        """
        Upserts a protocol with all its related data.
        
        Args:
            peptide_id: Peptide ID
            am_id: Administration method ID
            protocol_data: Protocol data
            dosages: List of dosage data
            reconstitution_steps: List of steps
            quality_indicators: List of indicators
        
        Returns:
            Protocol ID
        """
        protocol_id = self.protocol.upsert(peptide_id, am_id, protocol_data)
        
        if dosages:
            for dosage in dosages:
                self.dosage.upsert_protocol_dosage(protocol_id, dosage)
        
        if reconstitution_steps:
            for step in reconstitution_steps:
                self.protocol.upsert_reconstitution_step(protocol_id, step)
        
        if quality_indicators:
            for indicator in quality_indicators:
                self.protocol.upsert_quality_indicator(protocol_id, indicator)
        
        return protocol_id

    def delete_peptide_full(self, slug: str) -> bool:
        """Delete a peptide and all its related data."""
        return self.peptide.delete_peptide_cascading(slug)


# Legacy DbManager compatibility wrapper
class DbManager:
    """
    Legacy DbManager wrapper for backward compatibility.
    All operations delegate to DbService repositories.
    
    This allows existing code to continue working while migrated code
    can use individual repositories directly.
    """
    
    def __init__(self, db_url: str):
        """Initialize with database URL (delegates to DbConnection)."""
        self.db_connection = DbConnection(db_url)
        self.service = DbService(self.db_connection)

    @property
    def conn(self):
        """Proxy to the underlying connection (stays current after connect())."""
        return self.db_connection.conn
    
    def connect(self):
        """For backward compatibility."""
        return self.db_connection.connect()
    
    def close(self):
        """For backward compatibility."""
        self.db_connection.close()
    
    # Delegate all operations to service
    
    def get_peptide_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        return self.service.peptide.get_by_slug(slug)

    def insert_lookup(self, table: str, name: str, **kwargs) -> int:
        return self.service.lookup.upsert(table, name, **kwargs)

    def upsert_research_study(self, study: Dict[str, Any]) -> int:
        return self.service.research_study.upsert(study)

    def upsert_citation(self, citation: Dict[str, Any]) -> int:
        return self.service.citation.upsert(citation)

    def upsert_peptide_reference(self, peptide_id: int, ref_type: str, ref_id: int):
        self.service.reference.upsert_peptide_reference(peptide_id, ref_type, ref_id)

    def upsert_peptide_fill_nulls(self, payload: Dict[str, Any]) -> int:
        return self.service.peptide.upsert_fill_nulls(payload)

    def get_lookup_id(self, table: str, name: str) -> Optional[int]:
        return self.service.lookup.get_id_by_name(table, name)

    def get_research_study_id(self, title: str) -> Optional[int]:
        return self.service.research_study.get_id_by_title(title)

    def get_citation_id(self, title: str) -> Optional[int]:
        return self.service.citation.get_id_by_title(title)

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

    def get_graph_data_for_visualization(self, peptide_id: int, method_name: str = "Injectable") -> Dict[str, Any]:
        return self.service.graph.get_visualization_data(peptide_id, method_name)

    def link_relation(self, table: str, fk1_col: str, fk1_val: int, fk2_col: str, fk2_val: int):
        self.service.reference.link_entities(table, fk1_col, fk1_val, fk2_col, fk2_val)

    def get_all_peptide_identifiers(self) -> set:
        """Fetch all existing peptide slugs and lowercase names for pre-filtering."""
        return self.service.peptide.get_all_identifiers()

    def delete_peptide_data(self, slug: str) -> bool:
        return self.service.delete_peptide_full(slug)


class DbPool:
    """
    Legacy DbPool wrapper for backward compatibility.
    Uses new DbPool from connection module.
    """
    
    def __init__(self, db_url: str, minconn: int = 1, maxconn: int = 5):
        from src.infrastructure.db.connection import DbPool as NewDbPool
        self._pool = NewDbPool(db_url, minconn, maxconn)
    
    def acquire(self):
        """Context manager that returns a DbService instead of raw connection."""
        class DbServiceContextManager:
            def __init__(self, pool):
                self.pool = pool
                self.cm = None
                self.conn = None
                self.service = None
            
            def __enter__(self):
                # pool is a NewDbPool instance; call acquire() directly on it
                self.cm = self.pool.acquire()
                self.conn = self.cm.__enter__()
                self.service = DbService(self.conn)
                return self.service
            
            def __exit__(self, *args):
                return self.cm.__exit__(*args)
        
        return DbServiceContextManager(self._pool)
    
    def close(self):
        """Close the pool."""
        self._pool.close()
