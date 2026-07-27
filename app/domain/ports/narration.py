"""`NarrationPort`: mandatory natural-language restatement of finished intelligence.

Implemented by `infrastructure.ai.narration_service.NarrationService`. This
is the *only* thing an AI is ever allowed to touch — the port takes a
complete, already-computed `WeatherIntelligence` and returns a `Narrative`;
it has no way to alter any computed field, rank a day, or change a score,
because those aren't part of its signature at all.

Narration is mandatory: every call must be produced by the configured LLM.
There is no deterministic fallback and no "disabled" state — a failure
(timeout, transport error, unavailability, or invalid/empty output) raises
`NarrationFailedError` instead of silently substituting a template.
"""

from abc import ABC, abstractmethod

from app.domain.entities.weather_intelligence import Narrative, WeatherIntelligence


class NarrationFailedError(Exception):
    """Raised when the LLM cannot produce a valid narration.

    Covers every failure mode: disabled/misconfigured (should not occur —
    `Settings` fails application startup first), timeout, transport error,
    repeated server errors, or invalid/empty output. The caller (a future
    use case) decides how to surface this as a request failure; the port
    itself never substitutes a fallback.
    """


class NarrationPort(ABC):
    """Produces a `Narrative` for a finished `WeatherIntelligence`. Never computes."""

    @abstractmethod
    async def narrate(
        self, intelligence: WeatherIntelligence, language: str = "en"
    ) -> Narrative:
        """Return a `Narrative` for `intelligence`, in `language`.

        Raises `NarrationFailedError` if the LLM cannot produce a valid
        narration for any reason. There is no fallback path.
        """
