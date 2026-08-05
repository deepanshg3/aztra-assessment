"""Reusable logging utilities for the project."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Optional

LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

DEFAULT_LEVEL: int = logging.INFO

_DEFAULT_NAME: str = "retail_sales"

_handler: Optional[logging.Handler] = None
_attach_lock: threading.Lock = threading.Lock()


def _build_handler() -> logging.Handler:
    """Return a stream handler configured with the project-wide format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler


def _shared_handler() -> logging.Handler:
    """Return the single process-wide handler, creating it on first use."""
    global _handler
    if _handler is None:
        _handler = _build_handler()
    return _handler


def _normalise_name(name: Optional[str]) -> str:
    """Coerce an arbitrary logger name into a valid, non-empty string."""
    if not isinstance(name, str) or not name.strip():
        return _DEFAULT_NAME
    return name.strip()


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name.

    Python's logging registry caches loggers by name, so every call site that
    asks for the same name receives the same instance. A single shared handler
    is attached only when the logger has no handlers yet, which prevents
    duplicate log lines across repeated imports and multiple modules.

    Args:
        name: Logger name, typically ``__name__``. Empty or non-string values
            fall back to the default project name.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    logger_name = _normalise_name(name)
    logger = logging.getLogger(logger_name)

    with _attach_lock:
        if not logger.handlers:
            logger.addHandler(_shared_handler())
            logger.setLevel(DEFAULT_LEVEL)
            logger.propagate = False

    return logger
