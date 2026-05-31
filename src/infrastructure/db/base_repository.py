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

    def log_operation(self, operation: str, table: str, details: str = ""):
        """Log database operation."""
        msg = f"  [{operation}] Table {table}"
        if details:
            msg += f": {details}"
        logger.info(msg)
