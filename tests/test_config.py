"""Unit tests for `infrastructure/config/settings.py` — offline, no network/DB."""

import pytest
from pydantic import ValidationError

from app.infrastructure.config.settings import get_settings

REQUIRED_ENV = {
    "API_KEYS": "dev_key_local",
    "DATABASE_URL": "postgresql+asyncpg://wis:wis@localhost:5432/wis",
    "REDIS_URL": "redis://localhost:6379/0",
}


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch, tmp_path):
    """Isolate every test from the developer's real `.env` and the settings cache."""
    monkeypatch.chdir(tmp_path)
    for key in REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_env(monkeypatch, **overrides: str) -> None:
    env = {**REQUIRED_ENV, **overrides}
    for key, value in env.items():
        monkeypatch.setenv(key, value)


class TestValidEnvironment:
    def test_valid_env_parses_with_documented_defaults(self, monkeypatch):
        _set_env(monkeypatch)
        settings = get_settings()

        assert settings.app_env == "local"
        assert settings.app_host == "0.0.0.0"
        assert settings.app_port == 8000
        assert settings.log_format == "console"
        assert settings.api_keys == ["dev_key_local"]
        assert settings.provider_priority_forecast == ["open_meteo", "openweather", "weatherapi"]
        assert settings.provider_priority_historical == ["meteostat"]
        assert settings.narration_enabled is True
        assert settings.rule_config_version == "2026.07"
        assert settings.max_forecast_horizon_days == 16

    def test_get_settings_is_cached(self, monkeypatch):
        _set_env(monkeypatch)
        assert get_settings() is get_settings()


class TestListParsing:
    def test_priority_string_parses_into_ordered_list(self, monkeypatch):
        _set_env(monkeypatch, PROVIDER_PRIORITY_FORECAST="weatherapi,open_meteo,openweather")
        settings = get_settings()
        assert settings.provider_priority_forecast == ["weatherapi", "open_meteo", "openweather"]

    def test_comma_separated_values_are_trimmed(self, monkeypatch):
        _set_env(monkeypatch, API_KEYS="key_one, key_two ,key_three")
        settings = get_settings()
        assert settings.api_keys == ["key_one", "key_two", "key_three"]

    def test_ops_api_keys_defaults_to_empty_list(self, monkeypatch):
        _set_env(monkeypatch)
        settings = get_settings()
        assert settings.ops_api_keys == []


class TestFailFast:
    def test_missing_single_required_variable_names_it(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", REQUIRED_ENV["DATABASE_URL"])
        monkeypatch.setenv("REDIS_URL", REQUIRED_ENV["REDIS_URL"])

        with pytest.raises(RuntimeError, match="API_KEYS"):
            get_settings()

    def test_missing_all_required_variables_names_each_one(self, monkeypatch):
        with pytest.raises(RuntimeError) as exc_info:
            get_settings()

        message = str(exc_info.value)
        assert "API_KEYS" in message
        assert "DATABASE_URL" in message
        assert "REDIS_URL" in message

    def test_empty_api_keys_is_rejected(self, monkeypatch):
        _set_env(monkeypatch, API_KEYS="")
        with pytest.raises(ValidationError):
            get_settings()


class TestValidation:
    @pytest.mark.parametrize(
        "var,value",
        [
            ("CACHE_TTL_PROVIDER_SECONDS", "-1"),
            ("CACHE_TTL_INTELLIGENCE_SECONDS", "0"),
            ("PROVIDER_HEALTH_TTL_SECONDS", "-10"),
            ("PROVIDER_TIMEOUT_SECONDS", "0"),
            ("RATE_LIMIT_PER_MINUTE", "0"),
            ("MAX_FORECAST_HORIZON_DAYS", "0"),
            ("LLM_MAX_OUTPUT_TOKENS", "-5"),
        ],
    )
    def test_non_positive_values_are_rejected(self, monkeypatch, var, value):
        _set_env(monkeypatch, **{var: value})
        with pytest.raises(ValidationError):
            get_settings()

    def test_invalid_app_env_is_rejected(self, monkeypatch):
        _set_env(monkeypatch, APP_ENV="not-a-real-env")
        with pytest.raises(ValidationError):
            get_settings()
