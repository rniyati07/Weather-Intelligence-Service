"""`TripContext` — the entity that lets a user stop repeating themselves.

The behaviour under test is almost entirely about *absence*: a follow-up turn
that mentions nothing must preserve everything, and a context that is missing
an essential must say which one rather than being silently unusable.
"""

from datetime import date

from app.domain.entities.trip import (
    MISSING_DESTINATION,
    MISSING_END_DATE,
    MISSING_START_DATE,
    GeocodedPlace,
    TripContext,
    parse_iso_date,
)

GOA = GeocodedPlace(
    name="Goa",
    latitude=15.29927,
    longitude=74.12401,
    country="India",
    country_code="IN",
    admin1="Goa",
    timezone="Asia/Kolkata",
)
PANJIM = GeocodedPlace(name="Panjim", latitude=15.4909, longitude=73.8278, country="India")

START = date(2026, 8, 20)
END = date(2026, 8, 23)


def complete_context() -> TripContext:
    return TripContext(destination=GOA, destination_query="Goa", start_date=START, end_date=END)


class TestGeocodedPlace:
    def test_location_id_is_the_backend_coordinate_format(self) -> None:
        assert GOA.location_id == "15.2993,74.1240"

    def test_display_name_includes_country(self) -> None:
        assert GOA.display_name == "Goa, India"

    def test_display_name_omits_absent_country(self) -> None:
        assert GeocodedPlace(name="Goa", latitude=1.0, longitude=2.0).display_name == "Goa"


class TestMissingEssentials:
    def test_empty_context_is_missing_everything_in_ask_order(self) -> None:
        assert TripContext().missing_essentials() == (
            MISSING_DESTINATION,
            MISSING_START_DATE,
            MISSING_END_DATE,
        )

    def test_complete_context_is_missing_nothing(self) -> None:
        assert complete_context().missing_essentials() == ()
        assert complete_context().is_complete is True

    def test_destination_query_alone_does_not_satisfy_destination(self) -> None:
        """An unresolved name is not a location — geocoding still has to run."""
        context = TripContext(destination_query="Goa", start_date=START, end_date=END)

        assert context.is_complete is False
        assert context.missing_essentials() == (MISSING_DESTINATION,)

    def test_partial_dates_report_only_the_absent_one(self) -> None:
        context = TripContext(destination=GOA, start_date=START)

        assert context.missing_essentials() == (MISSING_END_DATE,)


class TestMerge:
    def test_merge_returns_a_new_context_and_leaves_the_original_intact(self) -> None:
        original = TripContext()

        merged = original.merge(destination=GOA)

        assert merged is not original
        assert original.destination is None
        assert merged.destination == GOA

    def test_omitted_fields_are_preserved_not_cleared(self) -> None:
        """The whole point: "which day is best for beaches?" keeps the trip."""
        context = complete_context()

        merged = context.merge()

        assert merged.destination == GOA
        assert merged.start_date == START
        assert merged.end_date == END

    def test_supplied_fields_replace_previous_values(self) -> None:
        context = complete_context()

        merged = context.merge(destination=PANJIM, end_date=date(2026, 8, 25))

        assert merged.destination == PANJIM
        assert merged.end_date == date(2026, 8, 25)
        assert merged.start_date == START

    def test_a_turn_can_complete_a_context_incrementally(self) -> None:
        """"I'm going to Goa." then "August 20 to 23." — two turns, one trip."""
        context = TripContext().merge(destination=GOA, destination_query="Goa")
        assert context.is_complete is False

        context = context.merge(start_date=START, end_date=END)

        assert context.is_complete is True

    def test_interests_accumulate_across_turns(self) -> None:
        context = TripContext().merge(interests=["beaches"])

        merged = context.merge(interests=["museums"])

        assert merged.interests == ("beaches", "museums")

    def test_repeated_interests_are_not_duplicated(self) -> None:
        context = TripContext(interests=("beaches",))

        merged = context.merge(interests=["beaches", "museums"])

        assert merged.interests == ("beaches", "museums")

    def test_blank_interests_are_ignored(self) -> None:
        merged = TripContext().merge(interests=["  ", "beaches", ""])

        assert merged.interests == ("beaches",)

    def test_omitted_interests_are_preserved(self) -> None:
        context = TripContext(interests=("beaches",))

        assert context.merge(travel_style="relaxed").interests == ("beaches",)

    def test_travel_style_replaces_rather_than_accumulates(self) -> None:
        context = TripContext(travel_style="packed")

        assert context.merge(travel_style="relaxed").travel_style == "relaxed"


class TestParseIsoDate:
    """The one function standing between an LLM/JSONB string and a `date`
    field — regression coverage for the type bug that reached this exact
    boundary twice (LLM extraction, JSONB round-trip) before this existed."""

    def test_parses_a_valid_iso_string(self) -> None:
        assert parse_iso_date("2026-08-20") == date(2026, 8, 20)

    def test_date_object_passes_through_unchanged(self) -> None:
        assert parse_iso_date(START) is START

    def test_none_stays_none(self) -> None:
        assert parse_iso_date(None) is None

    def test_relative_phrase_is_dropped_not_guessed(self) -> None:
        """An LLM that ignores the "must be YYYY-MM-DD" instruction must not
        crash the merge — it must simply not have said anything."""
        assert parse_iso_date("next weekend") is None

    def test_empty_string_is_dropped(self) -> None:
        assert parse_iso_date("") is None

    def test_whitespace_only_is_dropped(self) -> None:
        assert parse_iso_date("   ") is None

    def test_non_date_type_is_dropped(self) -> None:
        assert parse_iso_date(12345) is None
        assert parse_iso_date(["2026-08-20"]) is None

    def test_surrounding_whitespace_is_tolerated(self) -> None:
        assert parse_iso_date("  2026-08-20  ") == date(2026, 8, 20)
