import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.v1.routers import api_router

from src.core.scheduler import start_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the pool on startup so the first request isn't slow
    from src.api.v1.endpoints.graph import get_pool
    get_pool()
    
    # Start the automated scheduler for background sync tasks
    start_scheduler()
    
    yield
    
    # Stop the automated scheduler cleanly on shutdown
    shutdown_scheduler()
    
    # Close all pool connections cleanly on shutdown
    from src.api.v1.endpoints.graph import _pool
    if _pool is not None:
        _pool.close()

app = FastAPI(title="Peptide Pipeline API and Graph Visualization", lifespan=lifespan)

# Get project root for static file path
project_root = os.path.dirname(os.path.abspath(__file__))
visualization_path = os.path.join(project_root, 'src', 'visualization')

# Mount static files for visualization
if os.path.exists(visualization_path):
    app.mount("/visualization", StaticFiles(directory=visualization_path, html=True), name="visualization")

# Include all the API endpoints
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def home():
    """Home page with information and links."""
    return HTMLResponse('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Peptide Pipeline API</title>
        <style>
            body { font-family: 'Inter', sans-serif; margin: 40px; line-height: 1.6; color: #333; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #2563eb; }
            .card { border: 1px solid #e5e7eb; padding: 20px; border-radius: 8px; background: #f9fafb; margin-bottom: 20px;}
            a { color: #2563eb; text-decoration: none; font-weight: 500; }
            a:hover { text-decoration: underline; }
            code { background: #fee2e2; padding: 2px 4px; border-radius: 4px; color: #991b1b; }
            ul { padding-left: 20px; }
            li { margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Peptide Pipeline API</h1>
            <div class="card">
                <p>Welcome to the consolidated Pharmacokinetics API & visualization engine.</p>
                <h3>System Capabilities:</h3>
                <ul>
                    <li><strong>Syncing:</strong> Scrape URLs (auto-discover or targeted) then sync to core or graph DB tables</li>
                    <li><strong>Evaluation:</strong> Testing ingestion robustness</li>
                    <li><strong>Visualization:</strong> Render Pharmacokinetics charts</li>
                </ul>
                <h3>Quick Links:</h3>
                <ul>
                    <li><strong>API Docs:</strong> <a href="/docs">Swagger UI / API Reference</a></li>
                    <li><strong>Viewer:</strong> <a href="/visualization/">Open Visualization Dashboard</a></li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    ''')

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
