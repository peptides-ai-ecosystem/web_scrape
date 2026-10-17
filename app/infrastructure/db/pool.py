"""The process-wide read connection pool used by the graph and core-data APIs.

Module-level connection pool (minconn=1, maxconn=5). Connections are checked
out per request and returned automatically via the ``DbPool.acquire()`` context
manager — no new TCP sockets per request, and each concurrent user gets their
own connection so cursors never collide.

The app's lifespan warms it on startup (``get_pool()``) and closes it on
shutdown (``close_pool()``).
"""

import os

from app.infrastructure.db.service import DbPool

_pool: DbPool | None = None


def get_pool() -> DbPool:
    global _pool
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    if _pool is None:
        _pool = DbPool(db_url, minconn=1, maxconn=5)
    return _pool


def close_pool() -> None:
    """Close all pool connections cleanly on shutdown (no-op when never opened)."""
    if _pool is not None:
        _pool.close()
