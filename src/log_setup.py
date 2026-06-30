"""
Simple production logging setup.

Configures Python's ``logging`` module once with three handlers:

================= ======= =================================
Handler           Level   Destination
================= ======= =================================
Console           INFO+   stdout (docker / systemd friendly)
Rotating file     DEBUG+  ``log/app.log``
Rotating file     ERROR+  ``log/error.log``
================= ======= =================================

Usage
-----
    from src.log_setup import get_logger

    logger = get_logger(__name__)
    logger.info("pipeline starting")
    logger.error("something went wrong")

The root logger is configured automatically when any module imports
:func:`get_logger` or :func:`setup_logging`.  Call :func:`setup_logging`
explicitly at application startup to control settings.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------
_LOG_FORMAT = "[%(asctime)s] [%(name)s] %(levelname)-5s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_FORMATTER = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

# ---------------------------------------------------------------------------
# One-shot configuration
# ---------------------------------------------------------------------------

def setup_logging(
    log_dir: str | Path = "log",
    level: int = logging.DEBUG,
    console_level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Configure the root logger with console + rotating file handlers.

    Safe to call multiple times — only configures the first time (subsequent
    calls are no-ops).
    """
    root = logging.getLogger()
    if root.hasHandlers():
        return  # already configured

    root.setLevel(level)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # --- Console handler (INFO+) -------------------------------------------
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(_FORMATTER)
    root.addHandler(console)

    # --- Rotating file handler – everything (DEBUG+) -----------------------
    app_handler = RotatingFileHandler(
        log_path / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.DEBUG)
    app_handler.setFormatter(_FORMATTER)
    root.addHandler(app_handler)

    # --- Rotating file handler – errors only (ERROR+) ----------------------
    err_handler = RotatingFileHandler(
        log_path / "error.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(_FORMATTER)
    root.addHandler(err_handler)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Return a logger for *name* (typically ``__name__``).

    Ensures :func:`setup_logging` has been called at least once so callers
    never have to worry about bootstrap order.
    """
    if not logging.getLogger().hasHandlers():
        setup_logging()
    return logging.getLogger(name)
