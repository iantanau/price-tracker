"""Structured logging configuration for the price tracker.

This module centralises logging setup so every component uses a consistent
format and log level. Avoid calling ``print()`` outside of application startup;
use the configured logger instead.
"""

import logging
import sys


DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure the root logger for the application.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR). Defaults to INFO.

    Returns:
        The configured root logger for the price tracker.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Reset handlers to avoid duplicate output if called multiple times.
    root_logger = logging.getLogger("price_tracker")
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))

    root_logger.addHandler(handler)
    root_logger.propagate = False

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Return a logger that is a child of the ``price_tracker`` namespace.

    Args:
        name: Module or component name, e.g. ``services.monitor_service``.

    Returns:
        A configured logger instance.
    """
    return logging.getLogger(f"price_tracker.{name}")
