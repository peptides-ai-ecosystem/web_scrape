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

app = FastAPI(
    title="Peptide Pipeline API & Graph Visualization",
    description="""
    **End-to-end peptide data pipeline** — scrape pharmacokinetics data from pep-pedia.org,
    synchronize to PostgreSQL, evaluate sync quality, and serve interactive graph visualizations.

    ## 🔄 Pipeline Capabilities

    ### 🕷️ Sync (Scrape → Database)
    | Endpoint | Description |
    |---|---|
    | `POST /api/v1/sync/core` | Scrape URLs → Sync to **core** DB tables (peptides, benefits, side-effects, dosages, protocols, interactions, indications, references) |
    | `POST /api/v1/sync/graph` | Scrape URLs → Sync to **graph** DB tables (pharmacokinetics SVG paths, markers, points) |
    | `POST /api/v1/sync/graph-missing` | Same as graph sync, but **only inserts missing** administration methods (idempotent) |

    ### 📊 Evaluation (CSV vs DB Comparison)
    | Endpoint | Description |
    |---|---|
    | `POST /api/v1/evaluation/core` | **13 checks** per peptide — existence, core fields, benefits, side-effects, dosages, schedules, admin methods, interactions, indications, protocols, references |
    | `POST /api/v1/evaluation/graph` | **5 checks** per peptide — graph rows exist, time-range coverage, SVG path populated, points populated, markers populated |

    ### 📈 Graph Data API
    | Endpoint | Description |
    |---|---|
    | `GET /api/v1/peptides` | List all peptides that have graph data available |
    | `GET /api/v1/peptide/{id}/methods` | List administration methods for a given peptide |
    | `GET /api/v1/graph/{id}?method=` | Full graph coordinates, SVG paths, markers, axis labels for rendering |

    ### 🧬 Core Data Inspector (DB read API)
    | Endpoint | Description |
    |---|---|
    | `GET /api/v1/core/peptides` | List all peptides currently in the database |
    | `GET /api/v1/core/peptide/{id}` | Fully normalized peptide record (benefits, side-effects, protocols, indications, references, graph summary) |
    | `GET /api/v1/core/peptide/by-slug/{slug}` | Same payload, keyed by slug — used to join CSV scrape against DB |
    | `GET /api/v1/core/lookups` | Every lookup catalog in one round-trip (administration_methods, benefits, side_effects, dosages, schedules, application_places, categories) |

    ### 📄 CSV Inspector (scrape read API)
    | Endpoint | Description |
    |---|---|
    | `GET /api/v1/csv/peptides` | Distinct `(name, method)` rows from `output/pep_pedia_master.csv` |
    | `GET /api/v1/csv/peptide?name=&method=` | Grouped, non-empty cells for one CSV row (parses embedded `graph_data_json`) |
    | `GET /api/v1/csv/columns` | All 2,400+ CSV columns bucketed by entity group |

    ### ⚙️ Operations & Job Management
    | Endpoint | Description |
    |---|---|
    | `GET /api/v1/operations/jobs?status=` | List all background jobs (optionally filtered) |
    | `GET /api/v1/operations/job/{id}` | Track a specific job's progress, result, or error |
    | `DELETE /api/v1/operations/job/{id}` | Cancel a pending or running job |
    | `GET /api/v1/operations/health` | System health check + job queue statistics |

    ### ⏰ Automated Scheduler
    | Endpoint | Description |
    |---|---|
    | `GET /api/v1/scheduler/status` | Check if the scheduler is running, its interval, and next run time |
    | `POST /api/v1/scheduler/start` | Start or reconfigure the background sync scheduler |
    | `POST /api/v1/scheduler/pause` | Pause the scheduler (without removing the job) |
    | `POST /api/v1/scheduler/resume` | Resume a paused scheduler |

    > **Note**: All long-running operations (sync, evaluation) run as **background tasks** and return a `job_id` immediately. Poll `/operations/job/{job_id}` to track progress.
    """,
    version="2.0.0",
    lifespan=lifespan,
    contact={
        "name": "Peptide Pipeline Team",
        "url": "https://github.com/sazzad1779-dev/web_scrape",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "Syncing",
            "description": "🕷️ Scrape peptide data from pep-pedia.org and sync to PostgreSQL database tables.",
        },
        {
            "name": "Evaluation",
            "description": "📊 Compare CSV expectations vs actual database state to measure sync quality.",
        },
        {
            "name": "Graph",
            "description": "📈 Retrieve pharmacokinetics graph data (SVG paths, markers, coordinates) for visualization.",
        },
        {
            "name": "Core Data",
            "description": "🧬 Read-only DB inspector — fetch every entity injected from the scrape (benefits, side-effects, protocols, indications, references, ...).",
        },
        {
            "name": "CSV Inspector",
            "description": "📄 Read-only CSV inspector — surface the raw scraped data in `output/pep_pedia_master.csv` grouped by entity.",
        },
        {
            "name": "Operations",
            "description": "⚙️ Track background jobs, cancel operations, and monitor system health.",
        },
        {
            "name": "Scheduler",
            "description": "⏰ Manage the automated background sync scheduler (start, pause, resume, status).",
        },
    ],
)

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
                    <li><strong>Pharmacokinetics:</strong> <a href="/visualization/">PK graph viewer</a></li>
                    <li><strong>Core data:</strong> <a href="/visualization/core.html">CSV vs DB inspector</a></li>
                    <li><strong>Operations:</strong> <a href="/visualization/dashboard.html">Sync / evaluation / scheduler dashboard</a></li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    ''')

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
