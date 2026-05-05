"""Structlog configuration for poe2-rpc.

Call configure_logging(settings) once at startup. Do NOT call
stdlib logging.basicConfig — structlog is the canonical interface.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
import structlog.contextvars

from poe2_rpc.infrastructure.settings import AppSettings

_LEVEL_MAP: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def _build_processors(use_console: bool) -> list[Any]:
    renderer: Any = (
        structlog.dev.ConsoleRenderer() if use_console else structlog.processors.JSONRenderer()
    )
    # stdlib processors (filter_by_level, add_logger_name) require a stdlib
    # Logger and fail with PrintLogger on Python 3.14+; use native equivalents.
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        renderer,
    ]


def configure_logging(settings: AppSettings) -> None:
    level = _LEVEL_MAP[settings.log_level]

    # Configure stdlib root logger so structlog's filter_by_level works.
    logging.root.setLevel(level)

    use_console = settings.log_format == "console" or sys.stdout.isatty()
    processors = _build_processors(use_console)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
