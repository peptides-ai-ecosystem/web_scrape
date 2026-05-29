import os
from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Add project root to path if needed for local imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.infrastructure.db_manager import DbManager

router = APIRouter(prefix="/api")

@router.get("/peptides")
async def get_peptides():
    """Get all peptides with available graph data."""
    db = DbManager(os.getenv("DATABASE_URL"))
    try:
        with db.connect().cursor() as cur:
            cur.execute("""
                SELECT DISTINCT p.id, p.name
                FROM peptides p
                JOIN peptide_graph pg ON p.id = pg.peptide_id
                ORDER BY p.name
            """)
            peptides = [{"id": row['id'], "name": row['name']} for row in cur.fetchall()]
        return peptides
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/peptide/{peptide_id}/methods")
async def get_peptide_methods(peptide_id: int):
    """Get all available administration methods for a peptide."""
    db = DbManager(os.getenv("DATABASE_URL"))
    try:
        methods = db.get_methods_for_peptide(peptide_id)
        return methods
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/graph/{peptide_id}")
async def get_graph_data(peptide_id: int, method: str = Query("Injectable")):
    """Fetch graph data for a peptide by ID and administration method."""
    db = DbManager(os.getenv("DATABASE_URL"))
    try:
        data = db.get_graph_data_for_visualization(peptide_id, method)
        if not data or not any(k not in ['peptide_name', 'administration_method'] for k in data.keys()):
            raise HTTPException(status_code=404, detail=f"No graph data found for peptide {peptide_id} with method {method}")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
