"""ASGI entrypoint. The container runs ``uvicorn main:app``; the app is built in ``app/factory.py``."""

import os

import uvicorn

from app.factory import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
