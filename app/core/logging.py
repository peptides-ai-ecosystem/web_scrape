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
    from app.core.logging import get_logger

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


# -------------------- LOGGING FUNCTIONS -------------------- #
# Backward-compatible wrappers so existing callers (log_debug, log_error)
# continue to work without any changes.  Under the hood they delegate to
# Python's standard logging module which writes to rotating files +
# console.  See the setup above for configuration details.

_log = get_logger("config")  # module-level logger for config.py itself


def log_error(message: str, filename: str | None = None) -> None:
    """Log an error message (backward-compatible wrapper)."""
    get_logger(filename or "app").error(message)


def log_warning(message: str, filename: str | None = None) -> None:
    """Log a warning message."""
    get_logger(filename or "app").warning(message)


def log_info(message: str, filename: str | None = None) -> None:
    """Log an info message."""
    get_logger(filename or "app").info(message)


def log_debug(message: str, filename: str | None = None) -> None:
    """Log a debug message (backward-compatible wrapper)."""
    get_logger(filename or "app").debug(message)


def log_success(message: str, filename: str | None = None) -> None:
    """Log a success signal at INFO level with a ✓ prefix."""
    get_logger(filename or "app").info(f"✓ {message}")


def clear_logs() -> None:
    """Clear both error and debug logs (no-op, kept for backward compat).

    Old behaviour wrote directly to ``error_log.txt`` / ``debug_log.txt``.
    The new rotating-file handlers manage this automatically, so this is now
    a no-op.
    """
    _log.info("clear_logs() called — rotating log files self-manage, ignoring.")
