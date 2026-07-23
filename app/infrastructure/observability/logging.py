"""Structured logging configuration.

JSON output in production, human-readable console output locally. Every
event automatically carries whatever `request_id` / `path` / `method` are
currently bound via `request_context.py`, and a redaction processor strips
known secret-bearing fields before a log line is ever rendered.
"""

import logging
import sys

import structlog
from structlog.types import EventDict

from app.infrastructure.config.settings import SECRET_FIELD_NAMES, Settings

_REDACTED = "***REDACTED***"

# Defense in depth beyond the named settings fields: catch anything whose key
# *looks* secret-shaped even if it was logged under a different name.
_SECRET_KEY_SUBSTRINGS = ("key", "secret", "token", "password", "authorization")


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return lowered in SECRET_FIELD_NAMES or any(s in lowered for s in _SECRET_KEY_SUBSTRINGS)


def redact_secrets_processor(logger: object, method_name: str, event_dict: EventDict) -> EventDict:
    """Structlog processor: replace any secret-shaped key's value before rendering."""
    for key in event_dict:
        if _looks_secret(key):
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structlog for the process. Call once, at application startup."""
    log_level = getattr(logging, settings.log_level)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_secrets_processor,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
