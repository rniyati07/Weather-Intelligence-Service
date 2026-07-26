"""Loads a rule config YAML file from disk and validates it into a `RuleConfig`.

This is the *only* place rule configuration touches the filesystem — the
domain layer's `parse_rule_config` is a pure function over already-loaded
data, kept I/O-free on purpose (`domain/rules/config.py`).
"""

from functools import lru_cache
from pathlib import Path

import yaml

from app.domain.rules.config import RuleConfig, RuleConfigError, parse_rule_config

_RULE_CONFIG_DIR = Path(__file__).parent / "rule_config"


def load_rule_config(version: str) -> RuleConfig:
    """Read and validate `infrastructure/config/rule_config/{version}.yaml`."""
    path = _RULE_CONFIG_DIR / f"{version}.yaml"
    if not path.is_file():
        raise RuleConfigError(f"no rule config file for version '{version}' at {path}")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise RuleConfigError(f"{path} did not parse to a mapping")

    config = parse_rule_config(data)
    if config.version != version:
        raise RuleConfigError(
            f"{path} declares version '{config.version}', filename implies '{version}'"
        )
    return config


@lru_cache
def get_rule_config(version: str) -> RuleConfig:
    """Return the cached, validated `RuleConfig` for `version` (constructed once)."""
    return load_rule_config(version)
