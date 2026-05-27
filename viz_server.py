import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from src.routes.graph import router as graph_router

app = FastAPI(title="Peptide Graph Visualization")

# Get project root for static file path
project_root = os.path.dirname(os.path.abspath(__file__))
visualization_path = os.path.join(project_root, 'src', 'visualization')

# Mount static files for visualization
app.mount("/visualization", StaticFiles(directory=visualization_path, html=True), name="visualization")

# Include the API router
app.include_router(graph_router)

@app.get("/")
async def home():
    """Home page with information and links."""
    return HTMLResponse('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Graph Visualization Server</title>
        <style>
            body { font-family: 'Inter', sans-serif; margin: 40px; line-height: 1.6; color: #333; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #2563eb; }
            .card { border: 1px solid #e5e7eb; padding: 20px; border-radius: 8px; background: #f9fafb; }
            a { color: #2563eb; text-decoration: none; font-weight: 500; }
            a:hover { text-decoration: underline; }
            code { background: #fee2e2; padding: 2px 4px; border-radius: 4px; color: #991b1b; }
            ul { padding-left: 20px; }
            li { margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Peptide Graph Visualization Server</h1>
            <div class="card">
                <p>Welcome to the Pharmacokinetics visualization engine.</p>
                <h3>Quick Links:</h3>
                <ul>
                    <li><strong>Viewer:</strong> <a href="/visualization/">Open Visualization Dashboard</a></li>
                    <li><strong>API Docs:</strong> <a href="/docs">Swagger UI / API Reference</a></li>
                </ul>
                <p>To view a specific peptide, use the UI selector or navigate directly:</p>
                <code>/visualization/?peptideId=[ID]&method=[Method]</code>
            </div>
        </div>
    </body>
    </html>
    ''')

if __name__ == "__main__":
    uvicorn.run("viz_server:app", host="0.0.0.0", port=5000, reload=True)
