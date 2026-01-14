"""Module for defining our logger."""

import logging
import logging.config
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import structlog
from pythonjsonlogger.json import JsonFormatter
from structlog import make_filtering_bound_logger
from structlog.contextvars import merge_contextvars
from structlog.dev import set_exc_info
from structlog.processors import StackInfoRenderer, TimeStamper, add_log_level
from structlog.stdlib import LoggerFactory

if TYPE_CHECKING:
    from collections.abc import Mapping


def setup_logging(log_dir: Path = Path("logs"), log_level: int = logging.INFO) -> None:
    """Configure structured logging suitable for a production server.

    Uses structlog for rich, JSON-compatible logs with console rendering for development.
    Supports file rotation and proper levels.
    """
    level: Final[int] = log_level

    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    # Standard library logging config for file handler with rotation
    logging_config: Mapping[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": JsonFormatter, "format": "%(asctime)s %(name)s %(levelname)s %(message)s"}},
        "handlers": {
            "file": {
                "class": RotatingFileHandler,
                "level": level,
                "formatter": "json",
                "filename": log_dir / "server.log",
                "maxBytes": 10_000_000,  # 10MB
                "backupCount": 5,
            },
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "json",
            },
        },
        "root": {"level": level, "handlers": ["file", "console"]},
    }

    logging.config.dictConfig(logging_config)

    # Structlog configuration on top
    structlog.configure(
        cache_logger_on_first_use=True,
        logger_factory=LoggerFactory(),
        wrapper_class=make_filtering_bound_logger(level),
        processors=[
            merge_contextvars,
            add_log_level,
            StackInfoRenderer(),
            set_exc_info,
            TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),  # Production JSON
        ],
        context_class=dict,
    )
