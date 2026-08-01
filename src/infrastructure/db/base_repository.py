"""Base repository with common database operations."""
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
import psycopg2
import logging

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base class for all repositories with common database operations."""

    def __init__(self, connection):
        """
        Initialize repository with a database connection.
        
        Args:
            connection: psycopg2 connection object or DbConnection/DbPool.
        """
        self.connection = connection

    @contextmanager
    def get_cursor(self):
        """
        Context manager for database cursor.
        Automatically handles connection acquisition for different connection types.
        """
        # Handle DbConnection (single connection)
        if hasattr(self.connection, 'connect'):
            conn = self.connection.connect()
        # Handle raw psycopg2 connection
        else:
            conn = self.connection

        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def _commit(self):
        """Commit transaction."""
        if hasattr(self.connection, 'conn'):
            # DbConnection object
            self.connection.conn.commit()
        else:
            # Raw psycopg2 connection
            self.connection.commit()

    def _rollback(self):
        """Rollback transaction."""
        if hasattr(self.connection, 'conn'):
            # DbConnection object
            self.connection.conn.rollback()
        else:
            # Raw psycopg2 connection
            self.connection.rollback()

    def execute_one(self, query: str, params: tuple) -> Optional[Dict[str, Any]]:
        """Execute query and fetch one row."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def execute_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and fetch all rows."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def execute_scalar(self, query: str, params: tuple) -> Optional[Any]:
        """Execute query and fetch single value (first column of first row)."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if row is None:
                return None
            # psycopg2 with RealDictCursor returns RealDictRow (dict-like)
            return list(row.values())[0]

    def execute_update(self, query: str, params: tuple) -> int:
        """Execute update/insert/delete query and return row count."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            self._commit()
            return cur.rowcount

    def _insert_guarded(self, cursor, table: str, columns: List[str], params: List[Any]) -> Optional[int]:
        """
        Insert a row into ``table`` and return the new ``id``.

        If the insert fails with a primary-key ``UniqueViolation`` — caused by
        a desynced ``id`` sequence after a pg_dump restore that included
        explicit ids — the aborted transaction is rolled back and the insert
        is retried once with an explicit ``id = MAX(id) + 1``.

        This is a **pure-code** workaround: it never calls ``setval`` and never
        alters the schema, so it works regardless of the sequence's state and
        leaves the database untouched. While a sequence stays desynced, each
        insert pays one extra rollback + MAX() query and then succeeds.
        """
        cols = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        insert_sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING id"
        try:
            cursor.execute(insert_sql, params)
            return cursor.fetchone()["id"]
        except psycopg2.errors.UniqueViolation:
            self._rollback()
            try:
                cursor.execute(f"SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM {table}")
                next_id = cursor.fetchone()["next_id"]
                cursor.execute(
                    f"INSERT INTO {table} (id, {cols}) VALUES ({', '.join(['%s'] * (len(columns) + 1))}) RETURNING id",
                    [next_id] + list(params),
                )
                return cursor.fetchone()["id"]
            except Exception:
                # Leave the transaction in a clean state for the caller.
                self._rollback()
                raise

    def log_operation(self, operation: str, table: str, details: str = ""):
        """Log database operation."""
        msg = f"  [{operation}] Table {table}"
        if details:
            msg += f": {details}"
        logger.info(msg)
