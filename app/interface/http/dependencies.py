"""Shared FastAPI dependencies: settings injection and (later) auth, query params.

Application code receives configuration through this dependency rather than
importing `infrastructure.config.settings` directly, so routes and use cases
stay decoupled from *how* settings are constructed and remain overridable in
tests via `app.dependency_overrides`.
"""

from typing import Annotated

from fastapi import Depends

from app.infrastructure.config.settings import Settings, get_settings


def get_app_settings() -> Settings:
    """FastAPI dependency returning the process-wide, cached `Settings`."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
