"""Typed, fail-fast application configuration.

Every environment variable in the API & Data Contract's supporting guide
(§4.1) is represented here as a typed field. This is the only module in the
codebase permitted to read environment variables; everything else receives
configuration through :func:`get_settings` (directly or via the FastAPI
dependency in ``interface/http/dependencies.py``).
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

CsvList = Annotated[list[str], NoDecode]

SECRET_FIELD_NAMES = frozenset(
    {
        "api_keys",
        "ops_api_keys",
        "openweather_api_key",
        "weatherapi_key",
        "meteostat_api_key",
        "llm_api_key",
    }
)


def _split_csv(value: object) -> object:
    """Parse a comma-separated env string into a list, before pydantic validation."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Application configuration, loaded once at startup from the environment.

    Required fields (no default) cause a fail-fast error at construction time
    if the corresponding environment variable is absent — see
    :func:`get_settings` for the friendly error message this produces.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    app_env: Literal["local", "staging", "production"] = "local"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, gt=0, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    # ---- Auth ----
    api_keys: CsvList = Field(...)
    ops_api_keys: CsvList = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=60, gt=0)

    # ---- Database ----
    database_url: PostgresDsn
    db_pool_size: int = Field(default=10, gt=0)
    db_max_overflow: int = Field(default=5, ge=0)

    # ---- Cache ----
    redis_url: RedisDsn
    cache_backend: Literal["redis", "memory"] = "redis"
    cache_ttl_provider_seconds: int = Field(default=3600, gt=0)
    cache_ttl_intelligence_seconds: int = Field(default=10800, gt=0)

    # ---- Weather providers ----
    openweather_api_key: str = ""
    weatherapi_key: str = ""
    meteostat_api_key: str = ""
    provider_priority_forecast: CsvList = Field(
        default_factory=lambda: ["open_meteo", "openweather", "weatherapi"]
    )
    provider_priority_historical: CsvList = Field(default_factory=lambda: ["meteostat"])
    provider_timeout_seconds: float = Field(default=5, gt=0)
    provider_retry_attempts: int = Field(default=2, ge=0)
    provider_retry_backoff_seconds: float = Field(default=0.3, ge=0)
    provider_health_ttl_seconds: int = Field(default=60, gt=0)

    # ---- AI narration ----
    narration_enabled: bool = True
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: float = Field(default=8, gt=0)
    llm_max_output_tokens: int = Field(default=400, gt=0)

    # ---- Domain rules ----
    rule_config_version: str = "2026.07"
    max_forecast_horizon_days: int = Field(default=16, gt=0)

    @field_validator(
        "api_keys",
        "ops_api_keys",
        "provider_priority_forecast",
        "provider_priority_historical",
        mode="before",
    )
    @classmethod
    def _parse_csv_list(cls, value: object) -> object:
        return _split_csv(value)

    @field_validator("api_keys")
    @classmethod
    def _api_keys_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("must contain at least one key")
        return value


def _missing_variable_message(exc: Exception) -> str | None:
    """Build a message naming every required env var missing from `exc`, if any."""
    from pydantic import ValidationError

    if not isinstance(exc, ValidationError):
        return None

    missing = [str(error["loc"][0]).upper() for error in exc.errors() if error["type"] == "missing"]
    if not missing:
        return None

    names = ", ".join(missing)
    return (
        f"Missing required environment variable(s): {names}. "
        "Set them in your environment or in a .env file (see .env.example)."
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide `Settings` instance, constructed on first call.

    Fails fast with a clear, variable-naming error if a required environment
    variable (`API_KEYS`, `DATABASE_URL`, `REDIS_URL`) is missing.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:  # noqa: BLE001 - re-raised with a clearer message below
        message = _missing_variable_message(exc)
        if message is not None:
            raise RuntimeError(message) from exc
        raise
