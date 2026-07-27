"""`NarrationPort`: optional natural-language restatement of finished intelligence.

Implemented by `infrastructure.ai.narration_service.NarrationService`. This
is the *only* thing an AI is ever allowed to touch — the port takes a
complete, already-computed `WeatherIntelligence` and returns a `Narrative`;
it has no way to alter any computed field, rank a day, or change a score,
because those aren't part of its signature at all. With narration disabled
or failing for any reason, the caller still gets a `Narrative` back (a
deterministic fallback) — this port never raises for narration failure.
"""

from abc import ABC, abstractmethod

from app.domain.entities.weather_intelligence import Narrative, WeatherIntelligence


class NarrationPort(ABC):
    """Produces a `Narrative` for a finished `WeatherIntelligence`. Never computes."""

    @abstractmethod
    async def narrate(
        self, intelligence: WeatherIntelligence, language: str = "en"
    ) -> Narrative:
        """Return a `Narrative` for `intelligence`, in `language`.

        Never raises for a narration failure (disabled, missing key,
        timeout, transport error, invalid/empty output) — every such case
        yields a deterministic fallback `Narrative` instead.
        """
