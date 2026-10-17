"""Database infrastructure module."""
from app.infrastructure.db.connection import DbConnection
from app.infrastructure.db.connection import DbPool as NewDbPool
from app.repositories.base import BaseRepository
from app.repositories import (
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
from app.infrastructure.db.service import DbService, DbManager, DbPool

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
