# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - LOGGER
# Logging configuration
# ═══════════════════════════════════════════════════════════════

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler
from rich.console import Console


def setup_logger(
    name: str = "polymarket_bot",
    level: str = "INFO",
    log_file: Optional[str] = None,
    rich_console: bool = True
) -> logging.Logger:
    """
    Setup logging with Rich console output

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        rich_console: Use Rich console for output

    Returns:
        Configured logger
    """
    # Configure root logger to capture all module logs
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    if rich_console:
        # Force UTF-8 encoding for Windows
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')

        console = Console(force_terminal=True, legacy_windows=False)
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            markup=True
        )
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Return the named logger
    logger = logging.getLogger(name)
    return logger


def get_logger(name: str = "polymarket_bot") -> logging.Logger:
    """Get existing logger or create new one"""
    return logging.getLogger(name)