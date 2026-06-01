"""
DbConnectionV2 — Optimized single-connection manager.

Fix applied vs v1:
  - Removed the `SELECT 1` ping on every cursor acquisition.
    v1 fired a full network round-trip to Supabase for every call to
    `get_cursor()`. Here we only check `conn.closed` (an in-process
    flag) and only reconnect when the socket is provably broken.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import time

logger = logging.getLogger(__name__)


class DbConnectionV2:
    """
    Lightweight single-connection wrapper.

    Differences from v1 DbConnection:
    - No SELECT 1 ping — avoids a network round-trip on every cursor open.
    - Reconnects only when psycopg2 marks the connection closed.
    - Exposes `begin()` / `commit()` / `rollback()` for explicit transaction
      control used by the v2 orchestrator.
    """

    def __init__(self, db_url: str, connect_timeout: int = 10):
        self.db_url = db_url
        self.connect_timeout = connect_timeout
        self.conn = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> "psycopg2.connection":
        """
        Return the existing connection if open, otherwise create a new one.
        No SELECT 1 ping — we rely on psycopg2's `closed` attribute which is
        an in-process flag (no network I/O).
        """
        if self.conn and not self.conn.closed:
            return self.conn

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"[db_v2] Connecting to database (attempt {attempt + 1}/{max_retries})")
                self.conn = psycopg2.connect(
                    self.db_url,
                    cursor_factory=RealDictCursor,
                    connect_timeout=self.connect_timeout,
                )
                # Use manual transaction control (autocommit=False is the default)
                self.conn.autocommit = False
                logger.info("[db_v2] Connection established.")
                return self.conn
            except psycopg2.OperationalError as e:
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # 1s, 2s back-off
                    logger.warning(f"[db_v2] Connection attempt {attempt + 1} failed, retry in {delay}s: {str(e)[:100]}")
                    time.sleep(delay)
                else:
                    logger.error("[db_v2] Could not connect after all retries.")
                    raise

    # ------------------------------------------------------------------
    # Transaction helpers (used by the v2 orchestrator)
    # ------------------------------------------------------------------

    def begin(self):
        """Ensure connection is open. psycopg2 starts a transaction implicitly."""
        self.connect()

    def commit(self):
        """Commit the current transaction."""
        if self.conn and not self.conn.closed:
            self.conn.commit()

    def rollback(self):
        """Roll back the current transaction."""
        if self.conn and not self.conn.closed:
            self.conn.rollback()

    def close(self):
        """Close the connection."""
        if self.conn and not self.conn.closed:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None
