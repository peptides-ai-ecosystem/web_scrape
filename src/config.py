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

    # ── Gateway integration settings ──────────────────────────────────────
    # Shared secret the orchestrator gateway presents in UPSTREAM_AUTH_HEADER.
    # When empty, API routes run open (local dev only).
    API_TOKEN: str = os.getenv("API_TOKEN", "")
    # Header that carries the gateway token.
    GATEWAY_AUTH_HEADER: str = os.getenv("GATEWAY_AUTH_HEADER", "X-Gateway-Token")
    # Start the APScheduler background sync on boot. Disable when the
    # orchestrator/gateway manages sync (default: on, preserves old behavior).
    START_SCHEDULER: bool = os.getenv("START_SCHEDULER", "true").strip().lower() in {"1", "true", "yes", "on"}
    
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
    
    # ── Competitor vendor scraping (peptides-platform#288) ────────────────
    # Targets live in a file, never in code, so a site can be removed or
    # paused without a deploy. Missing file == no targets == no scraping.
    VENDOR_TARGETS_FILE: Path = Path(
        os.getenv("VENDOR_TARGETS_FILE", "config/vendor_targets.json")
    )
    # Contact URL embedded in the User-Agent so a site owner who wants us to
    # stop has somewhere to go. Keep it real.
    VENDOR_SCRAPER_CONTACT_URL: str = os.getenv(
        "VENDOR_SCRAPER_CONTACT_URL",
        "https://github.com/peptides-ai-ecosystem/web_scrape",
    )
    # Honest, identifiable User-Agent. This is NOT the spoofed browser string
    # used by src/infrastructure/webdriver_factory.py for our own pep-pedia
    # scrape — competitor sites get told exactly who is calling.
    VENDOR_SCRAPER_USER_AGENT: str = os.getenv(
        "VENDOR_SCRAPER_USER_AGENT",
        f"PeptidesVendorScraper/1.0 (+{VENDOR_SCRAPER_CONTACT_URL})",
    )
    # Politeness floor, seconds between requests to the same host. The
    # effective delay is max(this, target override, robots.txt Crawl-delay).
    VENDOR_SCRAPE_MIN_INTERVAL_SECONDS: float = float(
        os.getenv("VENDOR_SCRAPE_MIN_INTERVAL_SECONDS", "5.0")
    )
    # Retries on 429/5xx before the host is abandoned for the run.
    VENDOR_SCRAPE_MAX_RETRIES: int = int(os.getenv("VENDOR_SCRAPE_MAX_RETRIES", "2"))
    VENDOR_SCRAPE_BACKOFF_SECONDS: float = float(
        os.getenv("VENDOR_SCRAPE_BACKOFF_SECONDS", "30.0")
    )
    VENDOR_SCRAPE_TIMEOUT_MS: int = int(os.getenv("VENDOR_SCRAPE_TIMEOUT_MS", "20000"))
    # Relative price move that flags an observation for review instead of
    # letting it overwrite a previously accepted price. 0.25 == 25%.
    VENDOR_PRICE_DELTA_THRESHOLD: float = float(
        os.getenv("VENDOR_PRICE_DELTA_THRESHOLD", "0.25")
    )
    # Below this confidence an observation is always flagged.
    VENDOR_MIN_CONFIDENCE: float = float(os.getenv("VENDOR_MIN_CONFIDENCE", "0.6"))
    # Nightly cron. Off by default — turn it on deliberately, per environment.
    VENDOR_SCRAPE_CRON_ENABLED: bool = os.getenv(
        "VENDOR_SCRAPE_CRON_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    VENDOR_SCRAPE_CRON_HOUR: int = int(os.getenv("VENDOR_SCRAPE_CRON_HOUR", "3"))
    VENDOR_SCRAPE_CRON_MINUTE: int = int(os.getenv("VENDOR_SCRAPE_CRON_MINUTE", "15"))
    # Publishing accepted observations onward into the platform's
    # `vendor_products` table. Off, and unimplemented — see
    # src/services/vendor_products_publisher.py for why.
    VENDOR_PRODUCTS_PUBLISH_ENABLED: bool = os.getenv(
        "VENDOR_PRODUCTS_PUBLISH_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}

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
API_TOKEN = settings.API_TOKEN
GATEWAY_AUTH_HEADER = settings.GATEWAY_AUTH_HEADER
START_SCHEDULER = settings.START_SCHEDULER
OUTPUT_DIR = settings.OUTPUT_DIR
ENHANCED_CSV = settings.ENHANCED_CSV
GRAPH_CSV = settings.GRAPH_CSV
FULL_CSV = settings.FULL_CSV
MASTER_CSV = settings.MASTER_CSV  # alias for ENHANCED_CSV (backward compat)
ERROR_LOG = settings.ERROR_LOG
DEBUG_LOG = settings.DEBUG_LOG
TIME_RANGES = settings.TIME_RANGES
BUTTON_SKIP_LIST = settings.BUTTON_SKIP_LIST

# Competitor vendor scraping (peptides-platform#288)
VENDOR_TARGETS_FILE = settings.VENDOR_TARGETS_FILE
VENDOR_SCRAPER_CONTACT_URL = settings.VENDOR_SCRAPER_CONTACT_URL
VENDOR_SCRAPER_USER_AGENT = settings.VENDOR_SCRAPER_USER_AGENT
VENDOR_SCRAPE_MIN_INTERVAL_SECONDS = settings.VENDOR_SCRAPE_MIN_INTERVAL_SECONDS
VENDOR_SCRAPE_MAX_RETRIES = settings.VENDOR_SCRAPE_MAX_RETRIES
VENDOR_SCRAPE_BACKOFF_SECONDS = settings.VENDOR_SCRAPE_BACKOFF_SECONDS
VENDOR_SCRAPE_TIMEOUT_MS = settings.VENDOR_SCRAPE_TIMEOUT_MS
VENDOR_PRICE_DELTA_THRESHOLD = settings.VENDOR_PRICE_DELTA_THRESHOLD
VENDOR_MIN_CONFIDENCE = settings.VENDOR_MIN_CONFIDENCE
VENDOR_SCRAPE_CRON_ENABLED = settings.VENDOR_SCRAPE_CRON_ENABLED
VENDOR_SCRAPE_CRON_HOUR = settings.VENDOR_SCRAPE_CRON_HOUR
VENDOR_SCRAPE_CRON_MINUTE = settings.VENDOR_SCRAPE_CRON_MINUTE
VENDOR_PRODUCTS_PUBLISH_ENABLED = settings.VENDOR_PRODUCTS_PUBLISH_ENABLED


# -------------------- LOGGING FUNCTIONS -------------------- #
# Backward-compatible wrappers so existing callers (log_debug, log_error)
# continue to work without any changes.  Under the hood they delegate to
# Python's standard logging module which writes to rotating files +
# console.  See ``src/log_setup.py`` for configuration details.

from src.log_setup import get_logger  # noqa: E402

_log = get_logger("config")  # module-level logger for config.py itself


def log_error(message: str, filename: Optional[str] = None) -> None:
    """Log an error message (backward-compatible wrapper)."""
    get_logger(filename or "app").error(message)


def log_warning(message: str, filename: Optional[str] = None) -> None:
    """Log a warning message."""
    get_logger(filename or "app").warning(message)


def log_info(message: str, filename: Optional[str] = None) -> None:
    """Log an info message."""
    get_logger(filename or "app").info(message)


def log_debug(message: str, filename: Optional[str] = None) -> None:
    """Log a debug message (backward-compatible wrapper)."""
    get_logger(filename or "app").debug(message)


def log_success(message: str, filename: Optional[str] = None) -> None:
    """Log a success signal at INFO level with a ✓ prefix."""
    get_logger(filename or "app").info(f"✓ {message}")


def clear_logs() -> None:
    """Clear both error and debug logs (no-op, kept for backward compat).

    Old behaviour wrote directly to ``error_log.txt`` / ``debug_log.txt``.
    The new rotating-file handlers manage this automatically, so this is now
    a no-op.
    """
    _log.info("clear_logs() called — rotating log files self-manage, ignoring.")
