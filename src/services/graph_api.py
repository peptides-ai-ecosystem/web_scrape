"""
FastAPI server to serve graph data from database to visualization frontend.
Usage: python src/services/graph_api.py
Then navigate to: http://localhost:5000/visualization/?peptideId=1&method=Injectable
"""

import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sys
import uvicorn

load_dotenv()

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.infrastructure.db_manager import DbManager

app = FastAPI(title="Graph Visualization API")

# Mount static files for visualization
visualization_path = os.path.join(project_root, 'src/visualization')
app.mount("/visualization", StaticFiles(directory=visualization_path, html=True), name="visualization")

@app.get("/api/peptides")
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

@app.get("/api/peptide/{peptide_id}/methods")
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

@app.get("/api/graph/{peptide_id}")
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


@app.get("/")
async def home():
    """Home page with link to visualization."""
    return HTMLResponse('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Graph Visualization API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
            .example { margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>Graph Visualization API</h1>
        <p>FastAPI server for graph data retrieval and visualization.</p>
        <h3>Quick Links:</h3>
        <ul>
            <li><a href="/visualization/?peptideId=258&method=Injectable">BPC-157 (Injectable)</a></li>
            <li><a href="/visualization/?peptideId=258&method=Oral">BPC-157 (Oral)</a></li>
            <li><a href="/docs">API Documentation (Swagger UI)</a></li>
            <li><a href="/redoc">Alternative API Docs (ReDoc)</a></li>
        </ul>
        <h3>API Endpoint:</h3>
        <p><code>GET /api/graph/{peptide_id}?method={method}</code></p>
        <p>Parameters:</p>
        <ul>
            <li><code>peptide_id</code>: Numeric peptide ID (e.g., 258 for BPC-157)</li>
            <li><code>method</code>: Administration method (e.g., Injectable, Oral, Nasal, Topical, etc.)</li>
        </ul>
        <h3>Example peptides:</h3>
        <ul class="example">
            <li>258: BPC-157</li>
            <li>5-Amino-1MQ</li>
        </ul>
    </body>
    </html>
    ''')

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=5000)
