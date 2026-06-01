"""
BaseRepositoryV2 — Context-aware cursor manager without per-call commits.

Key fix vs v1 BaseRepository:
  - `get_cursor()` does NOT call `_commit()` — all commits are deferred to
    the orchestrator which wraps each peptide row in a single transaction.
  - `execute_update()` no longer auto-commits, keeping all writes in the
    same transaction opened by the orchestrator.
"""
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class BaseRepositoryV2:
    """
    Base repository for v2 — all writes stay in the caller's transaction.

    The connection passed in is expected to be a DbConnectionV2 instance
    or a raw psycopg2 connection. No commit is issued here; only the
    orchestrator calls conn.commit() once per peptide row.
    """

    def __init__(self, connection):
        self.connection = connection

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_conn(self):
        """Return the underlying psycopg2 connection."""
        if hasattr(self.connection, "connect"):
            # DbConnectionV2 — call connect() to ensure socket is open
            return self.connection.connect()
        return self.connection

    @contextmanager
    def get_cursor(self):
        """
        Open a cursor on the current connection.
        No ping, no autocommit — the caller owns the transaction.
        """
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def execute_one(self, query: str, params: tuple) -> Optional[Dict[str, Any]]:
        """Execute a SELECT and return the first row (or None)."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def execute_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT and return all rows."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def execute_scalar(self, query: str, params: tuple) -> Optional[Any]:
        """Execute a SELECT and return the first column of the first row."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if row is None:
                return None
            return list(row.values())[0]

    def execute_write(self, query: str, params: tuple) -> int:
        """
        Execute an INSERT/UPDATE/DELETE.
        Does NOT commit — the transaction is owned by the orchestrator.
        Returns rowcount.
        """
        with self.get_cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount

    def execute_returning(self, query: str, params: tuple) -> Optional[Any]:
        """
        Execute a RETURNING query and return the first value of the first row.
        Does NOT commit.
        """
        with self.get_cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if row is None:
                return None
            return list(row.values())[0]

    def log_op(self, op: str, table: str, detail: str = ""):
        msg = f"  [v2/{op}] {table}"
        if detail:
            msg += f": {detail}"
        logger.debug(msg)
