"""Database connection management."""
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class DbConnection:
    """Single database connection with automatic reconnection logic."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = None
        self.last_used = 0
        self.timeout = 60  # Timeout connection after 60 seconds of disuse

    def connect(self):
        """Get a database connection, reusing if available and valid."""
        current_time = time.time()
        
        # Try to reuse existing connection
        if self.conn and not self.conn.closed:
            # Check if connection is still valid
            try:
                # Do a simple ping
                with self.conn.cursor() as cur:
                    cur.execute("SELECT 1")
                self.last_used = current_time
                return self.conn
            except (psycopg2.OperationalError, psycopg2.DatabaseError):
                # Connection is stale, close it
                try:
                    self.conn.close()
                except:
                    pass
                self.conn = None
        
        # Create new connection with retry logic
        max_retries = 2
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Creating new database connection (attempt {attempt + 1}/{max_retries})")
                self.conn = psycopg2.connect(
                    self.db_url,
                    cursor_factory=RealDictCursor,
                    connect_timeout=5
                )
                self.last_used = current_time
                return self.conn
            except psycopg2.OperationalError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed, retrying in {retry_delay}s: {str(e)[:80]}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to database after {max_retries} attempts")
                    raise

    def close(self):
        """Close the database connection."""
        if self.conn and not self.conn.closed:
            try:
                self.conn.close()
            except:
                pass
            self.conn = None


class DbPool:
    """
    Thread-safe connection pool backed by psycopg2.ThreadedConnectionPool.

    Each concurrent request checks out its own dedicated connection, uses it,
    then returns it — so connections are never shared between requests and
    no new TCP sockets are created per request.

    Usage:
        pool = DbPool(db_url, minconn=1, maxconn=5)

        with pool.acquire() as conn:
            cursor = conn.cursor()
            ...
    """

    def __init__(self, db_url: str, minconn: int = 1, maxconn: int = 5):
        self._db_url = db_url
        self._pool = ThreadedConnectionPool(
            minconn,
            maxconn,
            db_url,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
        )
        logger.info(f"DbPool created (minconn={minconn}, maxconn={maxconn}).")

    @contextmanager
    def acquire(self):
        """
        Context manager that yields a database connection from the pool.
        The connection is always returned to the pool on exit,
        even if an exception is raised.
        """
        conn = self._pool.getconn()
        try:
            yield conn
        except Exception:
            # Roll back any open transaction so the connection is clean on return
            try:
                if not conn.closed:
                    conn.rollback()
            except Exception:
                pass
            raise
        finally:
            # Always reset state and return connection to pool
            try:
                if not conn.closed:
                    conn.rollback()   # no-op if already committed; clears any open txn
            except Exception:
                pass
            self._pool.putconn(conn)

    def close(self):
        """Close all pooled connections (call on application shutdown)."""
        self._pool.closeall()
        logger.info("DbPool closed.")
