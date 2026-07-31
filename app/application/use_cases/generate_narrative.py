"""`GenerateNarrative` — narrate finished intelligence (API Spec §8.5).

The **only** caller of `NarrationPort` (guide §3.1). It computes the
deterministic intelligence first, then hands the finished object to the
narration port; the AI never participates in computing anything.

Narration is mandatory in this service (Phase 8 refactor): a failure raises
`NarrationFailedError` rather than substituting a fallback, and the HTTP
layer maps that to an error response.
"""

from dataclasses import dataclass
from datetime import date

from app.application.use_cases.get_weather_intelligence import GetWeatherIntelligence
from app.domain.entities.weather_intelligence import Narrative, Period, ResolvedLocation
from app.domain.ports.narration import NarrationPort


@dataclass(frozen=True, slots=True)
class NarrativeResult:
    """The narrated view plus the metadata the envelope needs."""

    location: ResolvedLocation
    period: Period
    narrative: Narrative
    cache_status: str
    degraded: bool
    rule_config_version: str


class GenerateNarrative:
    """Produces a `Narrative` for a location and date range."""

    def __init__(
        self, *, intelligence_use_case: GetWeatherIntelligence, narration: NarrationPort
    ) -> None:
        self._intelligence_use_case = intelligence_use_case
        self._narration = narration

    async def execute(
        self,
        *,
        latitude: float,
        longitude: float,
        start: date,
        end: date,
        language: str = "en",
        name: str | None = None,
    ) -> NarrativeResult:
        result = await self._intelligence_use_case.execute(
            latitude=latitude, longitude=longitude, start=start, end=end, name=name
        )
        narrative = await self._narration.narrate(result.intelligence, language)
        return NarrativeResult(
            location=result.intelligence.location,
            period=result.intelligence.period,
            narrative=narrative,
            cache_status=result.cache_status,
            degraded=result.degraded,
            rule_config_version=result.intelligence.rule_config_version,
        )
