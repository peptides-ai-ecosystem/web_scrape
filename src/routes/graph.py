import os
from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv
import sys
import logging

# Load environment variables
load_dotenv()

# Add project root to path if needed for local imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.infrastructure.db_manager import DbPool

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level connection pool (minconn=1, maxconn=5).
# Connections are checked out per request and returned automatically via the
# DbPool.acquire() context manager — no new TCP sockets per request, and each
# concurrent user gets their own connection so cursors never collide.
# ---------------------------------------------------------------------------
_pool: DbPool | None = None


def get_pool() -> DbPool:
    global _pool
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    if _pool is None:
        _pool = DbPool(db_url, minconn=1, maxconn=5)
    return _pool


@router.get("/peptides")
async def get_peptides():
    """Get all peptides with available graph data."""
    try:
        with get_pool().acquire() as db:
            with db.conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT p.id, p.name
                    FROM peptides p
                    JOIN peptide_graph pg ON p.id = pg.peptide_id
                    ORDER BY p.name
                """)
                peptides = [{"id": row['id'], "name": row['name']} for row in cur.fetchall()]
        return peptides
    except Exception as e:
        logger.error(f"Failed to fetch peptides: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/peptide/{peptide_id}/methods")
async def get_peptide_methods(peptide_id: int):
    """Get all available administration methods for a peptide."""
    try:
        with get_pool().acquire() as db:
            methods = db.get_methods_for_peptide(peptide_id)
        return methods
    except Exception as e:
        logger.error(f"Failed to fetch methods for peptide {peptide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/{peptide_id}")
async def get_graph_data(peptide_id: int, method: str = Query("Injectable")):
    """Fetch graph data for a peptide by ID and administration method."""
    try:
        with get_pool().acquire() as db:
            data = db.get_graph_data_for_visualization(peptide_id, method)
        if not data or not any(k not in ['peptide_name', 'administration_method'] for k in data.keys()):
            raise HTTPException(status_code=404, detail=f"No graph data found for peptide {peptide_id} with method {method}")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch graph data for peptide {peptide_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
