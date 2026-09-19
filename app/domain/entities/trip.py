"""`TripContext` and `GeocodedPlace` — what the assistant knows about a trip.

`TripContext` is the whole answer to "must the user repeat themselves?". It
accumulates across conversation turns: each message contributes whatever it
reveals, and the context reports what is still missing so the orchestrator can
ask rather than guess.

Frozen and merged-by-copy like every other domain entity, so a later turn can
never mutate the context an earlier one observed. Framework-free per guide
§3.2 — no pydantic, no ORM, no HTTP; the interface layer aliases these to
camelCase, exactly as it does for `WeatherIntelligence`.

Deliberately holds no validation: `end >= start`, the forecast horizon, and
the no-history rule all live in `interface/http/dependencies.validate_date_range`
and stay there, so there is one date-rule implementation rather than two.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date


def parse_iso_date(value: object) -> date | None:
    """Parse an ISO date from any source that may hand back a string, a
    `date`, or garbage — the one place this happens, reused by both the LLM
    extraction path (`chat_orchestrator.py`) and JSONB round-tripping
    (`persistence/repositories.py`), which fed raw strings straight into a
    `date`-typed field before this existed.

    Invalid input becomes `None`, never a crash and never a guess — the
    orchestrator treats a failed parse exactly like "not mentioned".
    """
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None

#: Essential fields, in the order the assistant should ask for them. A trip
#: cannot be answered without all three; everything else is enrichment.
MISSING_DESTINATION = "destination"
MISSING_START_DATE = "start_date"
MISSING_END_DATE = "end_date"


@dataclass(frozen=True, slots=True)
class GeocodedPlace:
    """A place name resolved to coordinates by the geocoding provider.

    Distinct from `weather_intelligence.ResolvedLocation`, which is the
    response-facing shape keyed by `"lat,lon"`: this one carries the
    provenance a *conversation* needs — the country and region that
    distinguish Goa, India from Goa, Camarines Sur.
    """

    name: str
    latitude: float
    longitude: float
    country: str | None = None
    country_code: str | None = None
    admin1: str | None = None
    timezone: str | None = None

    @property
    def location_id(self) -> str:
        """The `"{lat},{lon}"` id every weather endpoint already keys on.

        Formatted to 4dp to match what the frontend's geocoding produces, so
        the same place resolves to the same `locations.normalized_key` row
        whether it arrived through chat or through the dashboard.
        """
        return f"{self.latitude:.4f},{self.longitude:.4f}"

    @property
    def display_name(self) -> str:
        """Conversational label — "Goa, India"."""
        return ", ".join(part for part in (self.name, self.country) if part)


@dataclass(frozen=True, slots=True)
class TripContext:
    """Everything established about a trip so far, across all turns."""

    destination: GeocodedPlace | None = None
    #: The raw text the user used ("goa"), kept even after resolution so a
    #: follow-up can be understood and a failed lookup can be retried or
    #: quoted back verbatim when asking for a clarification.
    destination_query: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    #: A tuple, not a list, because this dataclass is frozen: an immutable
    #: default needs no `field(default_factory=...)` and cannot be aliased
    #: between two contexts by accident.
    interests: tuple[str, ...] = ()
    travel_style: str | None = None
    #: Free-text pace preference ("relaxed", "packed", ...) — enrichment,
    #: not an essential. Exists so "make it more relaxed" has somewhere to
    #: land and survives to the next turn's response-generation prompt.
    pace: str | None = None

    def missing_essentials(self) -> tuple[str, ...]:
        """Which of destination/start/end are still unknown, in ask-order."""
        missing: list[str] = []
        if self.destination is None:
            missing.append(MISSING_DESTINATION)
        if self.start_date is None:
            missing.append(MISSING_START_DATE)
        if self.end_date is None:
            missing.append(MISSING_END_DATE)
        return tuple(missing)

    @property
    def is_complete(self) -> bool:
        """True when weather intelligence can actually be requested."""
        return not self.missing_essentials()

    def merge(
        self,
        *,
        destination: GeocodedPlace | None = None,
        destination_query: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        interests: Sequence[str] | None = None,
        travel_style: str | None = None,
        pace: str | None = None,
    ) -> "TripContext":
        """Return a new context with every supplied value applied.

        `None` means "this turn said nothing about that field" — never "clear
        it". That distinction is the whole feature: "which day is best for
        beaches?" mentions no destination and no dates, and must leave both
        exactly as they were.

        Interests accumulate rather than replace, because "I like beaches"
        followed by "and museums" is additive in ordinary conversation.
        Everything else replaces, so "actually, make it the 22nd" wins.
        """
        merged_interests = self.interests
        if interests is not None:
            merged_interests = _dedupe(self.interests, interests)

        return replace(
            self,
            destination=destination if destination is not None else self.destination,
            destination_query=(
                destination_query if destination_query is not None else self.destination_query
            ),
            start_date=start_date if start_date is not None else self.start_date,
            end_date=end_date if end_date is not None else self.end_date,
            interests=merged_interests,
            travel_style=travel_style if travel_style is not None else self.travel_style,
            pace=pace if pace is not None else self.pace,
        )


def _dedupe(existing: Sequence[str], incoming: Sequence[str]) -> tuple[str, ...]:
    """Union preserving first-seen order, so the result is stable across turns."""
    seen: dict[str, None] = {}
    for item in (*existing, *incoming):
        cleaned = item.strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return tuple(seen)


__all__ = [
    "MISSING_DESTINATION",
    "MISSING_END_DATE",
    "MISSING_START_DATE",
    "GeocodedPlace",
    "TripContext",
]
