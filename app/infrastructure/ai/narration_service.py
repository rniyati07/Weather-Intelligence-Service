"""Fulfills `NarrationPort`: constrained-prompt LLM narration, mandatory.

Build prompt -> call LLM -> validate output -> `Narrative`. There is no
fallback path: every failure mode (timeout, transport error, repeated
server errors, or invalid/empty output) raises `NarrationFailedError`
instead of silently substituting a template. `Settings` requires
`LLM_API_KEY`/`LLM_MODEL`/`LLM_BASE_URL` at startup (Phase 2), so by the
time this module runs, a real `LlmClient` is always available.
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
from app.domain.ports.narration import NarrationFailedError, NarrationPort
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
    """Mandatory LLM narration behind `NarrationPort`, with a success cache.

    Only successful narrations are cached — a failure raises immediately
    and is never cached, so the next request retries the LLM rather than
    being stuck replaying a stale error.
    """

    def __init__(
        self,
        *,
        llm_client: LlmClientProtocol,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._llm_client = llm_client
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
        prompt = render_prompt(intelligence, language)
        try:
            raw_text = await self._llm_client.complete(
                system_prompt=prompt, user_content="Write the narration now."
            )
        except LlmTimeoutError as exc:
            logger.warning("narration_timeout")
            raise NarrationFailedError("Narration timed out.") from exc
        except LlmClientError as exc:
            logger.warning("narration_transport_failure", extra={"error": str(exc)})
            raise NarrationFailedError(f"Narration request failed: {exc}") from exc

        summary_text = raw_text.strip()
        if not summary_text:
            logger.warning("narration_invalid_output", extra={"reason": "empty"})
            raise NarrationFailedError("LLM returned empty narration output.")
        if len(summary_text) > _MAX_SUMMARY_LENGTH:
            logger.warning("narration_invalid_output", extra={"length": len(summary_text)})
            raise NarrationFailedError("LLM returned narration output over the length cap.")

        return Narrative(
            generated_by_llm=True,
            summary_text=summary_text,
            fallback_used=False,
            model_used=self._llm_client.model,
        )


def build_narration_service(settings: Settings, http_client: httpx.AsyncClient) -> NarrationService:
    """Wire an `LlmClient` from Phase 2 settings.

    `Settings` requires `LLM_API_KEY`/`LLM_MODEL`/`LLM_BASE_URL` at
    application startup, so this always constructs a real client — there is
    no "unconfigured" branch to fall back from.
    """
    llm_client = LlmClient(
        http_client,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
    )
    return NarrationService(llm_client=llm_client, http_client=http_client)


@lru_cache
def get_narration_service() -> NarrationService:
    """Return the process-wide `NarrationService`, constructed on first call."""
    settings = get_settings()
    http_client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
    return build_narration_service(settings, http_client)
