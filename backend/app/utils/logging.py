"""Structured application logging configuration using Python standard library logging."""

import logging
import sys
from typing import Optional


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure and initialize console logging for the application.

    Args:
        log_level: Logging level string ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').

    Returns:
        Configured root application logger.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # Configure top-level ddato logger
    app_logger = logging.getLogger("ddato")
    app_logger.setLevel(numeric_level)

    # Prevent handler duplication across reloads
    if not app_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        app_logger.addHandler(console_handler)

    return app_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Retrieve a child logger under the ddato namespace."""
    if name:
        return logging.getLogger(f"ddato.{name}")
    return logging.getLogger("ddato")
