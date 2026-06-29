import os
from pathlib import Path
from datetime import datetime
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
    LOG_DIR: Path = Path(os.getenv("LOG_DIR", "output"))
    LOG_DIR.mkdir(exist_ok=True)
    
    # File paths
    MASTER_CSV: Path = OUTPUT_DIR / "pep_pedia_master.csv"
    GRAPH_CSV: Path = OUTPUT_DIR / "pep_pedia_graph_master.csv"
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
MASTER_CSV = settings.MASTER_CSV
GRAPH_CSV = settings.GRAPH_CSV
ERROR_LOG = settings.ERROR_LOG
DEBUG_LOG = settings.DEBUG_LOG
TIME_RANGES = settings.TIME_RANGES
BUTTON_SKIP_LIST = settings.BUTTON_SKIP_LIST


# -------------------- LOGGING FUNCTIONS -------------------- #

def log_error(message: str, filename: Optional[str] = None) -> None:
    """
    Log an error message to ERROR_LOG with timestamp.
    
    Args:
        message: Error message to log
        filename: Optional filename prefix for per-file tracking
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {f'[{filename}] ' if filename else ''}{message}"
    
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"[WARNING] Failed to write to error log: {e}")


def log_debug(message: str, filename: Optional[str] = None) -> None:
    """
    Log a debug message to DEBUG_LOG with timestamp.
    
    Args:
        message: Debug message to log
        filename: Optional filename prefix for per-file tracking
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {f'[{filename}] ' if filename else ''}{message}"
    
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"[WARNING] Failed to write to debug log: {e}")


def clear_logs() -> None:
    """Clear both error and debug logs (useful at start of execution)."""
    try:
        ERROR_LOG.write_text("")
        DEBUG_LOG.write_text("")
        print(f"[INFO] Logs cleared at {ERROR_LOG} and {DEBUG_LOG}")
    except Exception as e:
        print(f"[WARNING] Failed to clear logs: {e}")
