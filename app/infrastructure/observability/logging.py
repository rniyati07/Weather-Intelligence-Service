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
from app.infrastructure.observability.redaction import REDACTED as _REDACTED
from app.infrastructure.observability.redaction import redact_text, redact_value

# Defense in depth beyond the named settings fields: catch anything whose key
# *looks* secret-shaped even if it was logged under a different name.
_SECRET_KEY_SUBSTRINGS = ("key", "secret", "token", "password", "authorization")


def _looks_secret(key: str) -> bool:
    lowered = key.lower()
    return lowered in SECRET_FIELD_NAMES or any(s in lowered for s in _SECRET_KEY_SUBSTRINGS)


def redact_secrets_processor(logger: object, method_name: str, event_dict: EventDict) -> EventDict:
    """Structlog processor: strip credentials before a line is ever rendered.

    Two passes, because they catch different mistakes. A secret-shaped *key*
    has its whole value replaced. Everything else has its *value* scanned for an
    embedded credential — that is what catches a provider URL logged under
    `error`, which no key-name rule would ever match.
    """
    for key in event_dict:
        if _looks_secret(key):
            event_dict[key] = _REDACTED
        else:
            event_dict[key] = redact_value(event_dict[key])
    return event_dict


class RedactingFilter(logging.Filter):
    """Scrub credentials from stdlib log records.

    `httpx` logs every request URL at INFO through the stdlib logger, bypassing
    structlog entirely — so the processor above never sees it. This filter sits
    on the root handler and catches those, plus anything else a dependency
    decides to log. It rewrites the message rather than dropping the record, so
    the endpoint, status and latency stay readable.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # The message is rendered first, then scrubbed. Redacting `msg` and
        # `args` separately does not work: `httpx` logs the URL as an
        # `httpx.URL` object, not a string, so a type-based walk of `args`
        # skips the very value that carries the credential.
        message = record.getMessage()
        redacted = redact_text(message)

        if redacted != message:
            # Only collapse to a pre-formatted string when something was
            # actually removed, so untouched records keep lazy formatting.
            record.msg = redacted
            record.args = ()

        return True


def configure_logging(settings: Settings) -> None:
    """Configure structlog for the process. Call once, at application startup."""
    log_level = getattr(logging, settings.log_level)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Attached to the handlers rather than to a logger: a filter on a logger
    # does not apply to records propagated from its children, and the leak we
    # care about originates in `httpx`.
    redacting_filter = RedactingFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redacting_filter)

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
