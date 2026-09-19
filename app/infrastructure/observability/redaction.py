"""Credential redaction for log output.

Key-name redaction (`logging.py`) only helps when a secret is logged *as* a
field. Two paths bypass it entirely:

1. **`httpx` logs every request URL at INFO**, through the stdlib logger rather
   than structlog — and several provider APIs authenticate with a query
   parameter, so the full credential lands in the log line:
   `HTTP Request: GET https://api.openweathermap.org/...?appid=<key>`

2. **Provider errors embed the URL in their message.** `ProviderError` is built
   from an `httpx` exception whose `str()` can include the request URL, and it
   is then logged under the innocuous key `error`.

This module scrubs the *values*, so both paths are covered without changing how
any request is made. Provider, endpoint, status, latency and request id all
survive — only the credential itself is replaced.
"""

import re

REDACTED = "***REDACTED***"

#: Query parameters that carry a credential. Several weather providers
#: authenticate this way, which is why URL logging is a leak at all.
_CREDENTIAL_QUERY_PARAMS = (
    "appid",
    "apikey",
    "api_key",
    "access_token",
    "auth",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
    "x-api-key",
)

#: `?key=value` / `&key=value`, up to the next separator. Case-insensitive
#: because providers are inconsistent about casing.
_QUERY_CREDENTIAL_RE = re.compile(
    r"(?P<prefix>[?&](?:" + "|".join(_CREDENTIAL_QUERY_PARAMS) + r")=)(?P<value>[^&\s\"'<>]+)",
    re.IGNORECASE,
)

#: `Authorization: Bearer xyz`, `Bearer xyz`, `X-API-Key: xyz`.
#:
#: The scheme is part of the *prefix*, not the value — otherwise
#: `Authorization: Bearer xyz` redacts the word "Bearer" and leaves the token
#: in the clear, which is worse than not redacting at all because it looks safe.
_HEADER_CREDENTIAL_RE = re.compile(
    r"(?P<prefix>"
    r"(?:authorization|x-api-key)\s*[:=]\s*(?:(?:bearer|basic)\s+)?"
    r"|(?:bearer|basic)\s+"
    r")(?P<value>[^\s\"',;]+)",
    re.IGNORECASE,
)


def redact_text(value: str) -> str:
    """Replace any credential embedded in `value`, leaving the rest intact."""
    redacted = _QUERY_CREDENTIAL_RE.sub(lambda m: f"{m.group('prefix')}{REDACTED}", value)
    return _HEADER_CREDENTIAL_RE.sub(lambda m: f"{m.group('prefix')}{REDACTED}", redacted)


def redact_value(value: object) -> object:
    """Recursively redact strings inside common log-value containers."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    return value
