"""Database infrastructure module."""

from app.infrastructure.db.connection import DbConnection
from app.infrastructure.db.connection import DbPool as NewDbPool
from app.infrastructure.db.service import DbManager, DbPool, DbService
from app.repositories import (
    CitationRepository,
    DosageRepository,
    GraphRepository,
    IndicationRepository,
    InteractionRepository,
    LookupRepository,
    PeptideRepository,
    ProtocolRepository,
    ReferenceRepository,
    ResearchStudyRepository,
)
from app.repositories.base import BaseRepository

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
