"""Weather-aware place ranking — the "lightweight travel intelligence" layer.

Deliberately not a rule engine: this reuses the *already-computed*
`activity_suitability` scores from the Insight Engine (Phase 7) and only adds
what those scores don't already express — mapping an `AttractionType` onto
the three `ActivityCategory` values the scores are keyed by, and turning a
numeric score into a `WeatherSuitability` band. No new weather thresholds are
introduced here; every number this module reads was decided elsewhere.

Pure and I/O-free, matching every other module under `domain/engines/`. The
places it ranks always came from a `PlacesPort` call made by the caller —
this module never fetches anything and never invents a place; a category
with no matching places in `places` simply contributes nothing to that day.
"""

from collections import defaultdict

from app.domain.entities.attractions import (
    Attraction,
    AttractionRecommendation,
    AttractionType,
    DailyAttractions,
    WeatherSuitability,
)
from app.domain.entities.place import RawPlace
from app.domain.entities.trip import TripContext
from app.domain.entities.weather_intelligence import DailyIntelligence, WeatherIntelligence
from app.domain.rules.config import ActivityCategory

#: `AttractionType` -> the `ActivityCategory` whose suitability score speaks
#: to it. Approximate by construction — the Insight Engine scores three
#: broad categories, not nineteen — but every `AttractionType` maps to
#: exactly one, so ranking is always well-defined.
_ATTRACTION_TO_ACTIVITY: dict[AttractionType, ActivityCategory] = {
    AttractionType.BEACH: "beach",
    AttractionType.WATER_SPORTS: "beach",
    AttractionType.ADVENTURE: "beach",
    AttractionType.MUSEUM: "indoor_museum",
    AttractionType.INDOOR_ACTIVITY: "indoor_museum",
    AttractionType.CULTURAL_SITE: "indoor_museum",
    AttractionType.WELLNESS: "indoor_museum",
    AttractionType.SHOPPING: "indoor_museum",
    AttractionType.NIGHTLIFE: "indoor_museum",
    AttractionType.RESTAURANT: "indoor_museum",
    AttractionType.FOOD: "indoor_museum",
    AttractionType.LANDMARK: "outdoor_sightseeing",
    AttractionType.VIEWPOINT: "outdoor_sightseeing",
    AttractionType.OUTDOOR_ACTIVITY: "outdoor_sightseeing",
    AttractionType.NATURE: "outdoor_sightseeing",
    AttractionType.WILDLIFE: "outdoor_sightseeing",
    AttractionType.FAMILY: "outdoor_sightseeing",
    AttractionType.PHOTOGRAPHY: "outdoor_sightseeing",
    AttractionType.HIKING: "outdoor_sightseeing",
    # A stay is a weather-shielded place, same category weight as an indoor
    # activity — not "beach"/"outdoor_sightseeing", which would tie a hotel's
    # suitability to conditions it isn't actually exposed to.
    AttractionType.HOTEL: "indoor_museum",
    AttractionType.GUEST_HOUSE: "indoor_museum",
    # Most `SPORTS_FACILITY` OSM tags (pitch, golf_course, stadium,
    # sports_centre) are outdoor venues; `WATER_SPORTS`/`HIKING`/`ADVENTURE`
    # already cover the sport categories that aren't.
    AttractionType.SPORTS_FACILITY: "outdoor_sightseeing",
}

#: Score-to-band thresholds. First threshold the score clears, high to low,
#: wins — mirrors the ordering convention `CONFIDENCE_BANDS` uses on the
#: frontend for the same kind of "numeric score -> plain label" mapping.
_SUITABILITY_BANDS: tuple[tuple[int, WeatherSuitability], ...] = (
    (75, WeatherSuitability.IDEAL),
    (55, WeatherSuitability.GOOD),
    (35, WeatherSuitability.NEUTRAL),
    (15, WeatherSuitability.POOR),
    (0, WeatherSuitability.UNSUITABLE),
)

#: Places offered per day, across all categories combined. Bounds prompt size
#: downstream and keeps a day's recommendations skimmable.
_MAX_PLACES_PER_DAY = 6


def _band_score(score: int) -> WeatherSuitability:
    for threshold, band in _SUITABILITY_BANDS:
        if score >= threshold:
            return band
    return WeatherSuitability.UNSUITABLE  # pragma: no cover - 0 is always covered above


def _score_for(day: DailyIntelligence, activity: ActivityCategory) -> int:
    for entry in day.activity_suitability:
        if entry.activity == activity:
            return entry.score
    return 50  # neutral default: a category the rule config doesn't score at all


def _weather_note(day: DailyIntelligence, score: int) -> str:
    """A deterministic sentence from real numbers — never an invented fact."""
    condition = day.summary.condition.value.replace("_", " ")
    return (
        f"{condition.capitalize()}, {day.summary.temp_min_c:.0f}-"
        f"{day.summary.temp_max_c:.0f}°C, {day.summary.precipitation_probability:.0%} "
        f"chance of rain (suitability {score}/100)."
    )


def _best_time(day: DailyIntelligence) -> str | None:
    """A conservative, deterministic time-of-day hint.

    Day-level weather only (hourly data is deferred), so this is
    intentionally coarse: it flags extreme-heat days for morning/evening
    visits and says nothing otherwise, rather than fabricating a claim about
    a specific hour this data cannot support.
    """
    if day.summary.temp_max_c >= 35:
        return "morning or evening"
    return None


def _to_attraction(day: DailyIntelligence, place: RawPlace, score: int) -> Attraction:
    return Attraction(
        id=place.source_id,
        name=place.name,
        type=place.category,
        description=f"{place.name}, a {place.category.value.replace('_', ' ')} near "
        f"{day.date.strftime('%b %d')}'s route.",
        latitude=place.latitude,
        longitude=place.longitude,
        address=place.address,
        weather_suitability=_band_score(score),
        weather_notes=_weather_note(day, score),
        best_time=_best_time(day),
        tags=place.tags,
    )


def rank_places_for_day(
    day: DailyIntelligence,
    places: list[RawPlace],
    *,
    limit: int = _MAX_PLACES_PER_DAY,
) -> tuple[Attraction, ...]:
    """Rank `places` for one day using that day's already-computed suitability scores.

    Pure: same `day` and `places` always produce the same ranked list. Ties
    break on name for a stable, reproducible order.

    Grouped round-robin by `AttractionType`, not a flat sort by score —
    live-observed: `_score_for` only ever returns one of three bucket scores
    (`_ATTRACTION_TO_ACTIVITY` maps nineteen types onto three), so a flat
    sort routinely ties many *different* categories together, and a category
    with more candidate places (say six sports facilities) then fills the
    entire day ahead of a category with fewer (two viewpoints, three
    landmarks) purely because it has more entries at the same score — not
    because it scored any better. An itinerary that successfully fetched
    real landmarks, viewpoints and sports facilities alongside food and
    museums still showed food/museum exclusively for exactly this reason.
    Visiting each category once per round, best-scoring categories first,
    means every category with any candidates left gets a fair turn before a
    populous one gets a second place — the fetch already did the work of
    finding a spread; the ranking must not throw it away.
    """
    scored: list[tuple[int, RawPlace]] = []
    for place in places:
        activity = _ATTRACTION_TO_ACTIVITY.get(place.category)
        score = _score_for(day, activity) if activity else 50
        scored.append((score, place))

    groups: dict[AttractionType, list[tuple[int, RawPlace]]] = defaultdict(list)
    for score, place in scored:
        groups[place.category].append((score, place))
    for group in groups.values():
        group.sort(key=lambda pair: (-pair[0], pair[1].name))

    # Categories visited best-score-first each round; a category name breaks
    # a tie between two categories whose best candidate scored the same.
    ordered_categories = sorted(
        groups, key=lambda category: (-groups[category][0][0], category.value)
    )

    attractions: list[Attraction] = []
    cursors = dict.fromkeys(ordered_categories, 0)
    while len(attractions) < limit:
        placed_this_round = False
        for category in ordered_categories:
            if len(attractions) >= limit:
                break
            cursor = cursors[category]
            group = groups[category]
            if cursor >= len(group):
                continue
            score, place = group[cursor]
            cursors[category] = cursor + 1
            attractions.append(_to_attraction(day, place, score))
            placed_this_round = True
        if not placed_this_round:
            break  # every category's candidates are exhausted

    return tuple(attractions)


def build_attraction_recommendation(
    *,
    trip_context: TripContext,
    weather_intelligence: WeatherIntelligence,
    places: list[RawPlace],
) -> AttractionRecommendation:
    """Assemble the full trip's day-by-day recommendations from real places.

    Every place in the result appeared in `places` — supplied by a
    `PlacesPort` call the caller already made. A day with no matching places
    for its interests simply gets an empty tuple; this function never
    substitutes a place that wasn't in its input.
    """
    location_id = weather_intelligence.location.id
    daily = tuple(
        DailyAttractions(
            date=day.date,
            location_id=location_id,
            attractions=rank_places_for_day(day, places),
        )
        for day in weather_intelligence.daily_intelligence
    )

    return AttractionRecommendation(
        location_id=location_id,
        period_start=weather_intelligence.period.start_date,
        period_end=weather_intelligence.period.end_date,
        daily=daily,
    )


def categories_by_frequency(places: list[RawPlace]) -> dict[AttractionType, int]:
    """How many places were found per category — diagnostic/testing helper."""
    counts: dict[AttractionType, int] = defaultdict(int)
    for place in places:
        counts[place.category] += 1
    return dict(counts)


__all__ = [
    "build_attraction_recommendation",
    "categories_by_frequency",
    "rank_places_for_day",
]
