"""Database infrastructure module."""
from src.infrastructure.db.connection import DbConnection
from src.infrastructure.db.connection import DbPool as NewDbPool
from src.infrastructure.db.base_repository import BaseRepository
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
from src.infrastructure.db.service import DbService, DbManager, DbPool

__all__ = [
    # Connection
    "DbConnection",
    "NewDbPool",
    # Service
    "DbService",
    # Legacy (backward compatibility)
    "DbManager",
    "DbPool",
    # Base
    "BaseRepository",
    # Repositories
    "PeptideRepository",
    "ProtocolRepository",
    "ResearchStudyRepository",
    "CitationRepository",
    "InteractionRepository",
    "IndicationRepository",
    "GraphRepository",
    "DosageRepository",
    "ReferenceRepository",
    "LookupRepository",
]
