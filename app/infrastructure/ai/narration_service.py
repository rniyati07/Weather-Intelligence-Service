"""Fulfills `NarrationPort`: constrained-prompt LLM narration with a
guaranteed deterministic fallback, and narration caching.

Build prompt -> call LLM -> validate output -> `Narrative`. Every failure
mode (disabled, missing key, timeout, transport error, invalid/empty
output) falls back to `fallback.build_fallback_narrative` instead of
raising — narration failure is never an exception the caller has to handle.
"""

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.domain.entities.weather_intelligence import Narrative, WeatherIntelligence
from app.domain.ports.narration import NarrationPort
from app.infrastructure.ai.fallback import build_fallback_narrative
from app.infrastructure.ai.llm_client import LlmClient, LlmClientError, LlmTimeoutError
from app.infrastructure.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class LlmClientProtocol(Protocol):
    """What `NarrationService` needs from an LLM client — not the concrete class.

    `LlmClient` satisfies this structurally; tests may supply any object
    with the same shape without subclassing it.
    """

    model: str

    async def complete(self, *, system_prompt: str, user_content: str) -> str: ...

_PROMPTS_DIR = Path(__file__).parent / "prompts"
#: Untrusted output: a hard length cap independent of (and a backstop for)
#: the model's own `LLM_MAX_OUTPUT_TOKENS` cap.
_MAX_SUMMARY_LENGTH = 2000

_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    autoescape=select_autoescape(disabled_extensions=("j2",)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _to_json_safe(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_json_safe(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    return obj


def render_prompt(intelligence: WeatherIntelligence, language: str) -> str:
    """Render the versioned narration prompt (never an inline string) as one system message."""
    template = _env.get_template("narration.j2")
    intelligence_json = json.dumps(_to_json_safe(intelligence), indent=2, sort_keys=True)
    return template.render(language=language, intelligence_json=intelligence_json)


CacheKey = tuple[str, str, str, str, str]


class NarrationService(NarrationPort):
    """LLM narration behind `NarrationPort`, with a guaranteed fallback and a cache."""

    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol | None,
        narration_enabled: bool,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._narration_enabled = narration_enabled
        self._http_client = http_client
        self._cache: dict[CacheKey, Narrative] = {}

    async def aclose(self) -> None:
        """Close the shared HTTP client, if this service constructed one."""
        if self._http_client is not None:
            await self._http_client.aclose()

    def _cache_key(self, intelligence: WeatherIntelligence, language: str) -> CacheKey:
        # (location, period, rule_config_version, language) per guide §Phase 8 step 7.
        return (
            intelligence.location.id,
            intelligence.period.start_date.isoformat(),
            intelligence.period.end_date.isoformat(),
            intelligence.rule_config_version,
            language,
        )

    async def narrate(self, intelligence: WeatherIntelligence, language: str = "en") -> Narrative:
        cache_key = self._cache_key(intelligence, language)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        narrative = await self._narrate_uncached(intelligence, language)
        self._cache[cache_key] = narrative
        return narrative

    async def _narrate_uncached(
        self, intelligence: WeatherIntelligence, language: str
    ) -> Narrative:
        if not self._narration_enabled or self._llm_client is None:
            return build_fallback_narrative(intelligence)

        try:
            prompt = render_prompt(intelligence, language)
            raw_text = await self._llm_client.complete(
                system_prompt=prompt, user_content="Write the narration now."
            )
        except LlmTimeoutError:
            logger.warning("narration_timeout")
            return build_fallback_narrative(intelligence)
        except LlmClientError as exc:
            logger.warning("narration_transport_failure", extra={"error": str(exc)})
            return build_fallback_narrative(intelligence)

        summary_text = raw_text.strip()
        if not summary_text or len(summary_text) > _MAX_SUMMARY_LENGTH:
            logger.warning("narration_invalid_output", extra={"length": len(summary_text)})
            return build_fallback_narrative(intelligence)

        return Narrative(
            generated_by_llm=True,
            summary_text=summary_text,
            fallback_used=False,
            model_used=self._llm_client.model,
        )


def build_narration_service(settings: Settings, http_client: httpx.AsyncClient) -> NarrationService:
    """Wire an `LlmClient` from Phase 2 settings, or `None` when narration can't run.

    `is_configured` here means: an API key, base URL, and model are all
    present. Missing any of them means the LLM client is never constructed
    and every call falls back — one of the guide's explicit fallback
    triggers ("API key is missing").
    """
    llm_client: LlmClient | None = None
    if settings.llm_api_key and settings.llm_base_url and settings.llm_model:
        llm_client = LlmClient(
            http_client,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )

    return NarrationService(
        llm_client=llm_client,
        narration_enabled=settings.narration_enabled,
        http_client=http_client,
    )


@lru_cache
def get_narration_service() -> NarrationService:
    """Return the process-wide `NarrationService`, constructed on first call."""
    settings = get_settings()
    http_client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
    return build_narration_service(settings, http_client)
