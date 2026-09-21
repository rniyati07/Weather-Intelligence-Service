"""Weather-aware place ranking — pure, built on the real Insight Engine output.

Uses `build_weather_intelligence` rather than hand-built `DailyIntelligence`
so these tests exercise the real mapping between an actual computed
suitability score and a `WeatherSuitability` band, not a mocked one.
"""

from datetime import date

from app.domain.engines.recommendation.attraction_matching import (
    build_attraction_recommendation,
    categories_by_frequency,
    rank_places_for_day,
)
from app.domain.entities.attractions import AttractionType, WeatherSuitability
from app.domain.entities.place import RawPlace
from app.domain.entities.trip import GeocodedPlace, TripContext
from app.domain.entities.weather_intelligence import (
    Period,
    ResolvedLocation,
    build_weather_intelligence,
)
from app.domain.rules.config import RuleConfig
from tests.domain.conftest import make_reading

GOA = GeocodedPlace(name="Goa", latitude=15.2993, longitude=74.1240, country="India")


def _intelligence(rule_config: RuleConfig, *, stormy: bool):
    reading = (
        make_reading(
            day=date(2026, 8, 1),
            temp_max_c=36.0,
            precipitation_probability=0.9,
            wind_speed_kph=45.0,
        )
        if stormy
        else make_reading(day=date(2026, 8, 1))
    )
    return build_weather_intelligence(
        location=ResolvedLocation(id="15.2993,74.1240", latitude=15.2993, longitude=74.1240),
        period=Period(start_date=date(2026, 8, 1), end_date=date(2026, 8, 1)),
        readings=[reading],
        rule_config=rule_config,
        as_of=date(2026, 7, 25),
    )


def _place(name: str, category: AttractionType, source_id: str | None = None) -> RawPlace:
    return RawPlace(
        source_id=source_id or f"node/{name}",
        name=name,
        category=category,
        latitude=15.30,
        longitude=74.12,
    )


class TestRankPlacesForDay:
    def test_clear_day_ranks_beach_ideal(self, rule_config: RuleConfig) -> None:
        intelligence = _intelligence(rule_config, stormy=False)
        day = intelligence.daily_intelligence[0]
        places = [_place("Calangute Beach", AttractionType.BEACH)]

        ranked = rank_places_for_day(day, places)

        assert len(ranked) == 1
        assert ranked[0].name == "Calangute Beach"
        assert ranked[0].weather_suitability in (
            WeatherSuitability.IDEAL,
            WeatherSuitability.GOOD,
        )

    def test_stormy_day_ranks_beach_worse_than_museum(self, rule_config: RuleConfig) -> None:
        intelligence = _intelligence(rule_config, stormy=True)
        day = intelligence.daily_intelligence[0]
        places = [
            _place("Calangute Beach", AttractionType.BEACH, "beach-1"),
            _place("Museum of Christian Art", AttractionType.MUSEUM, "museum-1"),
        ]

        ranked = rank_places_for_day(day, places)

        names_in_order = [p.name for p in ranked]
        assert names_in_order.index("Museum of Christian Art") < names_in_order.index(
            "Calangute Beach"
        )

    def test_never_fabricates_a_place_not_in_input(self, rule_config: RuleConfig) -> None:
        intelligence = _intelligence(rule_config, stormy=False)
        day = intelligence.daily_intelligence[0]

        ranked = rank_places_for_day(day, places=[])

        assert ranked == ()

    def test_result_is_capped_at_limit(self, rule_config: RuleConfig) -> None:
        intelligence = _intelligence(rule_config, stormy=False)
        day = intelligence.daily_intelligence[0]
        places = [
            _place(f"Beach {i}", AttractionType.BEACH, f"beach-{i}") for i in range(10)
        ]

        ranked = rank_places_for_day(day, places, limit=3)

        assert len(ranked) == 3

    def test_unmapped_category_gets_neutral_default(self, rule_config: RuleConfig) -> None:
        """A category with no `ActivityCategory` mapping still ranks, not crashes."""
        intelligence = _intelligence(rule_config, stormy=False)
        day = intelligence.daily_intelligence[0]

        ranked = rank_places_for_day(day, [_place("Some Landmark", AttractionType.LANDMARK)])

        assert len(ranked) == 1

    def test_pure_same_inputs_same_output(self, rule_config: RuleConfig) -> None:
        intelligence = _intelligence(rule_config, stormy=True)
        day = intelligence.daily_intelligence[0]
        places = [_place("A", AttractionType.BEACH), _place("B", AttractionType.MUSEUM, "b")]

        first = rank_places_for_day(day, places)
        second = rank_places_for_day(day, places)

        assert first == second


class TestBuildAttractionRecommendation:
    def test_one_daily_entry_per_forecast_day(self, rule_config: RuleConfig) -> None:
        intelligence = _intelligence(rule_config, stormy=False)
        trip_context = TripContext(
            destination=GOA, start_date=date(2026, 8, 1), end_date=date(2026, 8, 1)
        )

        result = build_attraction_recommendation(
            trip_context=trip_context,
            weather_intelligence=intelligence,
            places=[_place("Calangute Beach", AttractionType.BEACH)],
        )

        assert len(result.daily) == len(intelligence.daily_intelligence)
        assert result.location_id == intelligence.location.id

    def test_empty_places_yields_empty_days_not_error(self, rule_config: RuleConfig) -> None:
        intelligence = _intelligence(rule_config, stormy=False)
        trip_context = TripContext(
            destination=GOA, start_date=date(2026, 8, 1), end_date=date(2026, 8, 1)
        )

        result = build_attraction_recommendation(
            trip_context=trip_context, weather_intelligence=intelligence, places=[]
        )

        assert all(day.attractions == () for day in result.daily)


class TestNewAttractionCategories:
    """Stays and sports facilities reuse the existing 3-bucket suitability
    system (no new `ActivityCategory`) — a hotel scores exactly like a museum,
    and a sports facility exactly like a landmark, on the same day."""

    def test_hotel_and_guest_house_score_like_an_indoor_activity(
        self, rule_config: RuleConfig
    ) -> None:
        intelligence = _intelligence(rule_config, stormy=True)
        day = intelligence.daily_intelligence[0]
        places = [
            _place("City Museum", AttractionType.MUSEUM, "museum-1"),
            _place("Seaside Hotel", AttractionType.HOTEL, "hotel-1"),
            _place("Backpacker Guest House", AttractionType.GUEST_HOUSE, "guest-1"),
        ]

        ranked = {p.name: p.weather_suitability for p in rank_places_for_day(day, places)}

        assert ranked["Seaside Hotel"] == ranked["City Museum"]
        assert ranked["Backpacker Guest House"] == ranked["City Museum"]

    def test_sports_facility_scores_like_an_outdoor_activity(
        self, rule_config: RuleConfig
    ) -> None:
        intelligence = _intelligence(rule_config, stormy=False)
        day = intelligence.daily_intelligence[0]
        places = [
            _place("City Landmark", AttractionType.LANDMARK, "landmark-1"),
            _place("Town Sports Centre", AttractionType.SPORTS_FACILITY, "sports-1"),
        ]

        ranked = {p.name: p.weather_suitability for p in rank_places_for_day(day, places)}

        assert ranked["Town Sports Centre"] == ranked["City Landmark"]


class TestCategoriesByFrequency:
    def test_counts_by_category(self) -> None:
        places = [
            _place("A", AttractionType.BEACH, "a"),
            _place("B", AttractionType.BEACH, "b"),
            _place("C", AttractionType.MUSEUM, "c"),
        ]
        assert categories_by_frequency(places) == {
            AttractionType.BEACH: 2,
            AttractionType.MUSEUM: 1,
        }
