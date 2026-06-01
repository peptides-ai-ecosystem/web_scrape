"""
db_v2 — Optimized database layer.

Key improvements over db (v1):
  1. Single transaction per peptide row   → one commit instead of 30+
  2. ON CONFLICT upserts                  → no SELECT-before-INSERT round-trips
  3. No SELECT 1 connection ping          → removed per-cursor health check
  4. Connection reuse via DbConnectionV2  → stable single connection object
"""
from src.infrastructure.db_v2.service import DbServiceV2, DbManagerV2
from src.infrastructure.db_v2.connection import DbConnectionV2

__all__ = ["DbServiceV2", "DbManagerV2", "DbConnectionV2"]
