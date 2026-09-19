"""Rule-based intent classification — pure, no I/O."""

from datetime import date

from app.domain.entities.trip import GeocodedPlace, TripContext
from app.domain.rules.intent import ChatIntent, classify_intent

GOA = GeocodedPlace(name="Goa", latitude=15.2993, longitude=74.1240, country="India")
COMPLETE = TripContext(destination=GOA, start_date=date(2026, 8, 20), end_date=date(2026, 8, 23))
INCOMPLETE = TripContext()


class TestIncompleteContextAlwaysPlans:
    def test_any_message_is_trip_planning_when_context_incomplete(self) -> None:
        """Wording never overrides an incomplete context — nothing else is answerable yet."""
        assert classify_intent("which day is best for beaches?", INCOMPLETE) == (
            ChatIntent.TRIP_PLANNING
        )

    def test_planning_language_is_trip_planning(self) -> None:
        assert classify_intent("I'm planning a trip to Goa", INCOMPLETE) == (
            ChatIntent.TRIP_PLANNING
        )


class TestCompleteContextClassifiesByKeyword:
    def test_itinerary_keyword_wins_over_recommendation_keywords(self) -> None:
        """"itinerary" implies recommendations too — must be checked first."""
        assert classify_intent("give me a full itinerary with beaches", COMPLETE) == (
            ChatIntent.ITINERARY_REQUEST
        )

    def test_recommendation_keyword(self) -> None:
        assert classify_intent("which day is best for beaches?", COMPLETE) == (
            ChatIntent.RECOMMENDATION_REQUEST
        )

    def test_places_near_keyword(self) -> None:
        assert classify_intent("give me more places near Panjim", COMPLETE) == (
            ChatIntent.RECOMMENDATION_REQUEST
        )

    def test_weather_keyword(self) -> None:
        assert classify_intent("will it be windy tomorrow?", COMPLETE) == (
            ChatIntent.WEATHER_QUESTION
        )

    def test_what_can_i_do_if_it_rains_is_a_recommendation_request(self) -> None:
        """The spec's own example: this needs weather-aware *places*, not a
        bare forecast — "what can I do" is a recommendation ask, checked
        before the weather keywords for exactly this reason."""
        assert classify_intent("what can I do if it rains?", COMPLETE) == (
            ChatIntent.RECOMMENDATION_REQUEST
        )

    def test_no_keyword_match_is_general_chat(self) -> None:
        assert classify_intent("thanks, this is great", COMPLETE) == ChatIntent.GENERAL_CHAT

    def test_case_insensitive(self) -> None:
        assert classify_intent("BEACHES please", COMPLETE) == ChatIntent.RECOMMENDATION_REQUEST
