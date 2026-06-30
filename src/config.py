import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -------------------- SETTINGS -------------------- #

class Settings:
    """Application settings loaded from environment variables"""
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/peptides_db")

    # Selenium settings
    TIMEOUT: int = int(os.getenv("TIMEOUT", 5))
    
    # Directory settings
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "output"))
    OUTPUT_DIR.mkdir(exist_ok=True)
    LOG_DIR: Path = Path(os.getenv("LOG_DIR", "log"))
    LOG_DIR.mkdir(exist_ok=True)
    
    # File paths — manual sync flows use dedicated files to avoid race conditions
    ENHANCED_CSV: Path = OUTPUT_DIR / "pep_pedia_enhanced.csv"
    GRAPH_CSV: Path = OUTPUT_DIR / "pep_pedia_graph.csv"
    FULL_CSV: Path = OUTPUT_DIR / "pep_pedia_full.csv"
    # MASTER_CSV retained as alias for backward compat (data_summary.py, read_data.py)
    MASTER_CSV: Path = ENHANCED_CSV
    ERROR_LOG: Path = LOG_DIR / "error_log.txt"
    DEBUG_LOG: Path = LOG_DIR / "debug_log.txt"
    
    # Time range settings
    TIME_RANGES: list = ["24h", "7d", "14d", "30d"]
    
    # Skip list settings
    BUTTON_SKIP_LIST: list = [
        "peak", "half-life", "cleared", "hrs", "hr", "day",
    ] + TIME_RANGES


# -------------------- MODULE-LEVEL EXPORTS -------------------- #
# Create a default Settings instance for module-level imports
settings = Settings()

# Export settings for easy imports
DATABASE_URL = settings.DATABASE_URL
TIMEOUT = settings.TIMEOUT
OUTPUT_DIR = settings.OUTPUT_DIR
ENHANCED_CSV = settings.ENHANCED_CSV
GRAPH_CSV = settings.GRAPH_CSV
FULL_CSV = settings.FULL_CSV
MASTER_CSV = settings.MASTER_CSV  # alias for ENHANCED_CSV (backward compat)
ERROR_LOG = settings.ERROR_LOG
DEBUG_LOG = settings.DEBUG_LOG
TIME_RANGES = settings.TIME_RANGES
BUTTON_SKIP_LIST = settings.BUTTON_SKIP_LIST


# -------------------- LOGGING FUNCTIONS -------------------- #
# Backward-compatible wrappers so existing callers (log_debug, log_error)
# continue to work without any changes.  Under the hood they delegate to
# Python's standard logging module which writes to rotating files +
# console.  See ``src/log_setup.py`` for configuration details.

from src.log_setup import get_logger  # noqa: E402

_log = get_logger("config")  # module-level logger for config.py itself


def log_error(message: str, filename: Optional[str] = None) -> None:
    """Log an error message (backward-compatible wrapper).

    Delegates to ``logging.error()`` under the hood.
    """
    get_logger(filename or "app").error(message)


def log_debug(message: str, filename: Optional[str] = None) -> None:
    """Log a debug message (backward-compatible wrapper).

    Delegates to ``logging.debug()`` under the hood.
    """
    get_logger(filename or "app").debug(message)


def clear_logs() -> None:
    """Clear both error and debug logs (no-op, kept for backward compat).

    Old behaviour wrote directly to ``error_log.txt`` / ``debug_log.txt``.
    The new rotating-file handlers manage this automatically, so this is now
    a no-op.
    """
    _log.info("clear_logs() called — rotating log files self-manage, ignoring.")
