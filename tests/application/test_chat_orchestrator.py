"""`ChatOrchestrator` — mocked ports, no network, no database.

Covers the stabilization brief's required cases (happy path, partial
context, complete context, follow-up messages, extraction failures) plus a
regression test for every numbered bug the audit found in this module.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.application.use_cases.chat_orchestrator import ChatOrchestrator, EntityExtractor
from app.domain.entities.trip import TripContext
from app.domain.ports.geocoding import GeocodingUnavailableError
from app.domain.rules.intent import ChatIntent
from app.infrastructure.ai.llm_client import LlmClientError
from tests.application.conftest import (
    BANGALORE,
    CALANGUTE,
    GOA,
    KERALA,
    KOCHI,
    PANJIM,
    PARIS_FRANCE,
    PARIS_TEXAS,
    SPRINGFIELD_MISSOURI,
    FakeGeocoding,
    make_attraction_recommendation,
)

#: Computed relative to whenever the suite runs, not hardcoded — a fixed
#: date pair eventually lands in the past and gets rejected by the date-range
#: validation these tests are partly exercising (stabilization part 2).
_START = date.today() + timedelta(days=5)
_END = _START + timedelta(days=3)
_START_ISO = _START.isoformat()
_END_ISO = _END.isoformat()


def make_orchestrator(
    *,
    conversation_repo,
    geocoding,
    intelligence_use_case,
    attraction_provider,
    llm_client,
    max_forecast_horizon_days=16,
) -> ChatOrchestrator:
    return ChatOrchestrator(
        conversation_repo=conversation_repo,
        geocoding=geocoding,
        intelligence_use_case=intelligence_use_case,
        attraction_provider=attraction_provider,
        llm_client=llm_client,
        max_forecast_horizon_days=max_forecast_horizon_days,
    )


class TestPartialContext:
    async def test_missing_everything_asks_for_destination_first(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(conversation_id=None, user_message="hi there")

        assert result.context_complete is False
        assert "destination" in result.response.lower() or "where" in result.response.lower()
        # Neither expensive step ran — nothing to compute yet.
        assert intelligence_use_case.call_count == 0
        assert attraction_provider.call_count == 0
        assert llm_client.chat_call_count == 0

    async def test_destination_known_but_dates_missing_asks_for_dates(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = '{"destination": "Goa"}'

        result = await orchestrator.process_message(
            conversation_id=None, user_message="I want to visit Goa"
        )

        assert result.context_complete is False
        assert result.conversation.trip_context.destination == GOA
        assert "start" in result.response.lower() or "when" in result.response.lower()


class TestCompleteContextHappyPath:
    async def test_full_pipeline_runs_and_produces_llm_response(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None,
            user_message="I'm planning a 4-day trip to Goa from August 20 to August 23",
        )

        assert result.context_complete is True
        assert result.conversation.trip_context.start_date == _START
        assert result.conversation.trip_context.end_date == _END
        assert intelligence_use_case.call_count == 1
        assert attraction_provider.call_count == 1  # trip_planning intent fetches both
        assert result.llm_generated is True
        assert result.response == llm_client.chat_response
        assert conversation_repo.save_count == 1


class TestFollowUpMessages:
    """The user should not have to repeat destination and dates."""

    async def test_second_message_reuses_context_without_extraction_regressing_it(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = '{"destination": "Goa"}'
        first = await orchestrator.process_message(conversation_id=None, user_message="Goa")
        assert first.context_complete is False

        llm_client.extraction_response = (
            f'{{"startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        second = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="August 20 to 23"
        )

        assert second.context_complete is True
        assert second.conversation.trip_context.destination == GOA
        assert len(second.conversation.messages) == 4  # 2 user + 2 assistant turns

    async def test_recommendation_follow_up_does_not_require_new_destination_or_dates(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        """"Which day is best for beaches?" — no destination/date phrase at all."""
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, August 20 to 23"
        )
        assert first.context_complete is True
        geocoding.queries.clear()

        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="which day is best for beaches?"
        )

        assert result.context_complete is True
        assert result.intent == ChatIntent.RECOMMENDATION_REQUEST
        assert result.conversation.trip_context.destination == GOA
        assert geocoding.queries == []  # no re-geocoding on a follow-up


class TestIntentBasedFetchSkipping:
    """Step 3: a follow-up should not re-run the full pipeline."""

    async def test_general_chat_skips_weather_and_attractions(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        await orchestrator.process_message(conversation_id=None, user_message="Goa, Aug 20-23")
        intelligence_use_case.call_count = 0  # reset after the planning turn
        attraction_provider.call_count = 0

        result = await orchestrator.process_message(
            conversation_id=(await conversation_repo.get_active_for_user())[0].id,
            user_message="thanks so much!",
        )

        assert result.intent == ChatIntent.GENERAL_CHAT
        assert intelligence_use_case.call_count == 0
        assert attraction_provider.call_count == 0

    async def test_weather_question_also_fetches_places(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        """Master prompt, capability example: "What happens if it rains? ->
        use weather + weather-appropriate places" — a weather question is
        implicitly asking what to do about the weather, and the existing
        weather-aware ranking already surfaces indoor/good-weather options
        first on a poor-weather day. Unlike Revision 1's behaviour, this is
        no longer skipped."""
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, Aug 20-23"
        )
        intelligence_use_case.call_count = 0
        attraction_provider.call_count = 0

        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="will it be windy?"
        )

        assert result.intent == ChatIntent.WEATHER_QUESTION
        assert intelligence_use_case.call_count == 1
        assert attraction_provider.call_count == 1

    async def test_packing_request_fetches_weather_but_not_places(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        """Packing comes entirely from already-computed intelligence — no
        place lookup applies."""
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, Aug 20-23"
        )
        intelligence_use_case.call_count = 0
        attraction_provider.call_count = 0

        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="what should I pack?"
        )

        assert result.intent == ChatIntent.PACKING_REQUEST
        assert intelligence_use_case.call_count == 1
        assert attraction_provider.call_count == 0


class TestExtractionFailures:
    async def test_llm_extraction_failure_falls_back_gracefully(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        """A message the heuristic can't confidently parse, and the LLM call
        itself fails — must still produce a clarification, never crash."""
        llm_client.raise_on_extraction = LlmClientError("upstream 500")
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="something vague and unparseable"
        )

        assert result.context_complete is False
        assert result.conversation.trip_context.destination is None

    async def test_llm_extraction_returns_non_json_falls_back_gracefully(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        llm_client.extraction_response = "not json at all"
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="something vague and unparseable"
        )

        assert result.context_complete is False

    async def test_geocoding_failure_does_not_crash_the_turn(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        failing_geocoding = FakeGeocoding(error=GeocodingUnavailableError("provider down"))
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=failing_geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="I want to visit Goa"
        )

        # Destination stays unresolved — asked again, never guessed.
        assert result.context_complete is False
        assert result.conversation.trip_context.destination is None


class TestGracefulLlmDegradation:
    """Approved decision 1: /chat degrades to structured data, unlike /narrative."""

    async def test_chat_response_llm_failure_falls_back_to_structured_summary(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        llm_client.raise_on_chat = LlmClientError("Gemini unavailable")
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, August 20 to 23"
        )

        assert result.context_complete is True  # weather/attraction data still computed
        assert result.llm_generated is False
        assert "trip" in result.response.lower()  # structured fallback, not an error page

    async def test_empty_llm_response_also_falls_back(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        llm_client.chat_response = "   "
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, August 20 to 23"
        )

        assert result.llm_generated is False


class TestDateExtractionRegression:
    """Bug 2: LLM returns ISO date strings; must never reach TripContext raw."""

    async def test_llm_extracted_dates_become_real_date_objects(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, August 20 to 23"
        )

        assert isinstance(result.conversation.trip_context.start_date, date)
        assert isinstance(result.conversation.trip_context.end_date, date)
        # The use case must receive real dates too — a str would TypeError
        # inside date arithmetic the moment it reached the weather engine.
        assert intelligence_use_case.last_call["start"] == _START
        assert intelligence_use_case.last_call["end"] == _END

    async def test_malformed_llm_date_is_dropped_not_stored_as_a_string(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        llm_client.extraction_response = '{"destination": "Goa", "startDate": "next weekend"}'
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa next weekend"
        )

        assert result.conversation.trip_context.start_date is None
        assert result.context_complete is False


class TestYearlessDateResolution:
    """The extraction prompt anchors year-less dates ("September 10 to
    September 13") against today's date so the model has a year to resolve
    against. The actual resolution reasoning happens inside the LLM and
    isn't deterministically testable offline — what's ours to test is the
    prompt content we hand it (today's date, the resolution rule) and that
    `_llm_extract` wires in the real clock, not a fake one.
    """

    def test_prompt_states_todays_date(self, llm_client):
        extractor = EntityExtractor(llm_client)

        prompt = extractor._build_extraction_prompt(TripContext(), (), today=date(2026, 9, 6))

        assert "Today's date is 2026-09-06." in prompt

    def test_prompt_includes_the_yearless_resolution_rule(self, llm_client):
        extractor = EntityExtractor(llm_client)

        prompt = extractor._build_extraction_prompt(TripContext(), (), today=date(2026, 9, 6))

        assert "without a year" in prompt
        assert "already passed this year" in prompt
        assert "next year" in prompt

    @pytest.mark.parametrize(
        "today",
        [
            date(2026, 12, 31),  # last day of the year
            date(2027, 1, 1),  # first day of the year
            date(2026, 1, 1),  # first day of a different year
            date(2026, 12, 28),  # a "January 5" trip must roll to next year
        ],
    )
    def test_prompt_states_todays_date_around_year_boundaries(self, llm_client, today):
        extractor = EntityExtractor(llm_client)

        prompt = extractor._build_extraction_prompt(TripContext(), (), today=today)

        assert f"Today's date is {today.isoformat()}." in prompt

    async def test_extract_wires_in_the_real_current_date_not_a_stale_one(self, llm_client):
        extractor = EntityExtractor(llm_client)

        await extractor.extract("Goa next week", TripContext(), ())

        # UTC, matching `_llm_extract`'s own clock. Asserting on the local
        # `date.today()` made this fail for anyone east of UTC whenever their
        # local date had already rolled over — a timezone bug in the test,
        # not in the prompt.
        system_prompt = llm_client.calls[0][0]
        assert f"Today's date is {datetime.now(UTC).date().isoformat()}." in system_prompt


class TestDestinationHeuristicRegression:
    """The regex/keyword fallback, exercised via a forced Gemini-extraction
    failure (`raise_on_extraction`) — under the current architecture this
    path only ever runs when the primary Gemini extraction call itself
    fails, never as the default (see `EntityExtractor.extract`), so every
    test here sets that up explicitly rather than relying on it firing on
    its own.

    Bug 7: sentence-initial capitalization must not become the destination.

    Bug 8 (found via live frontend testing): joining *any* three
    non-stopword capitalized words in the message — not just an adjacent
    run of them — turned "Kerala in India" into the search query
    "Kerala India", which the real geocoder cannot resolve at all. Only a
    contiguous run may be joined; a real word (capitalized or not) between
    two candidates breaks it, while a comma does not, since "City, Country"
    is a legitimate single query shape the geocoder itself expects.
    """

    @pytest.mark.parametrize(
        "message,expected_query",
        [
            ("We are a family of 4 visiting Bali for 5 days", "Bali"),
            ("My friends and I want to go to Goa", "Goa"),
            ("I want to visit Kerala in India", "Kerala"),
            ("Planning a weekend in Bangalore", "Bangalore"),
            ("I'm planning a trip to New York", "New York"),
            ("I want to visit Kerala, India", "Kerala India"),
        ],
    )
    async def test_sentence_initial_word_is_excluded_from_destination(
        self,
        message,
        expected_query,
        conversation_repo,
        geocoding,
        intelligence_use_case,
        attraction_provider,
        llm_client,
    ):
        llm_client.raise_on_extraction = LlmClientError("Gemini unavailable")
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        await orchestrator.process_message(conversation_id=None, user_message=message)

        assert geocoding.queries == [expected_query]

    async def test_single_word_destination_still_resolves(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        llm_client.raise_on_extraction = LlmClientError("Gemini unavailable")
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        await orchestrator.process_message(conversation_id=None, user_message="Goa")

        assert geocoding.queries == ["Goa"]


class TestUnknownConversation:
    async def test_unknown_conversation_id_raises_value_error(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        from uuid import uuid4

        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        with pytest.raises(ValueError, match="not found"):
            await orchestrator.process_message(conversation_id=uuid4(), user_message="hi")


class TestSearchAreaOverride:
    """"Give me more places near Panjim" must recenter the attraction search
    without touching the trip's real, persisted destination."""

    async def _start_goa_conversation(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, trip planning"
        )
        assert first.context_complete is True
        geocoding.queries.clear()
        return orchestrator, first.conversation.id

    async def test_near_panjim_recenters_the_attraction_search(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"goa": [GOA], "panjim": [PANJIM]})
        orchestrator, conversation_id = await self._start_goa_conversation(
            conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
        )
        llm_client.extraction_response = (
            '{"searchArea": "Panjim", "intent": "recommendation_request"}'
        )

        result = await orchestrator.process_message(
            conversation_id=conversation_id, user_message="Give me more places near Panjim."
        )

        assert result.intent == ChatIntent.RECOMMENDATION_REQUEST
        assert attraction_provider.calls_trip_context[-1].destination == PANJIM

    async def test_more_places_in_calangute_recenters_the_attraction_search(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"goa": [GOA], "calangute": [CALANGUTE]})
        orchestrator, conversation_id = await self._start_goa_conversation(
            conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
        )
        llm_client.extraction_response = (
            '{"searchArea": "Calangute", "intent": "recommendation_request"}'
        )

        result = await orchestrator.process_message(
            conversation_id=conversation_id, user_message="more places in Calangute"
        )

        assert result.intent == ChatIntent.RECOMMENDATION_REQUEST
        assert attraction_provider.calls_trip_context[-1].destination == CALANGUTE

    async def test_trip_destination_is_never_replaced_by_a_search_area(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        """The literal requirement: Goa stays the trip destination — only
        the attraction search recenters, and only for that one turn."""
        geocoding = FakeGeocoding(results={"goa": [GOA], "panjim": [PANJIM]})
        orchestrator, conversation_id = await self._start_goa_conversation(
            conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
        )

        result = await orchestrator.process_message(
            conversation_id=conversation_id, user_message="Give me more places near Panjim."
        )

        assert result.conversation.trip_context.destination == GOA
        # Weather stays scoped to the trip destination, never the search area.
        assert intelligence_use_case.last_call["latitude"] == GOA.latitude
        assert intelligence_use_case.last_call["longitude"] == GOA.longitude

    async def test_search_area_does_not_persist_to_the_next_turn(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        """A one-off "near Panjim" question must not silently recenter
        every later question for the rest of the conversation."""
        geocoding = FakeGeocoding(results={"goa": [GOA], "panjim": [PANJIM]})
        orchestrator, conversation_id = await self._start_goa_conversation(
            conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
        )
        await orchestrator.process_message(
            conversation_id=conversation_id, user_message="Give me more places near Panjim."
        )

        await orchestrator.process_message(
            conversation_id=conversation_id, user_message="which day is best for beaches?"
        )

        assert attraction_provider.calls_trip_context[-1].destination == GOA

    async def test_no_search_area_phrase_uses_the_trip_destination(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator, conversation_id = await self._start_goa_conversation(
            conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
        )

        await orchestrator.process_message(
            conversation_id=conversation_id, user_message="which day is best for beaches?"
        )

        assert attraction_provider.calls_trip_context[-1].destination == GOA

    async def test_unresolvable_search_area_falls_back_to_trip_destination(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        """"near Nowheresville" — geocoding finds nothing for it; the
        attraction search must still run, scoped to the real destination,
        never crash and never silently drop the turn."""
        geocoding = FakeGeocoding(results={"goa": [GOA]})  # no entry for the area
        orchestrator, conversation_id = await self._start_goa_conversation(
            conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
        )

        result = await orchestrator.process_message(
            conversation_id=conversation_id, user_message="places near Nowheresville"
        )

        assert attraction_provider.calls_trip_context[-1].destination == GOA
        assert result.response  # still produced a response, didn't crash


class TestDateRangeValidation:
    """Stabilization part 2: chat must enforce the same date rules REST does,
    before any weather/provider I/O — never a duplicate rule implementation."""

    async def test_historical_range_is_rejected_before_any_fetch(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        past_start = (date.today() - timedelta(days=10)).isoformat()
        past_end = (date.today() - timedelta(days=6)).isoformat()
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{past_start}", "endDate": "{past_end}"}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, last week"
        )

        assert "forecast" in result.response.lower() or "upcoming" in result.response.lower()
        assert intelligence_use_case.call_count == 0
        assert attraction_provider.call_count == 0
        assert llm_client.chat_call_count == 0

    async def test_end_before_start_is_rejected_before_any_fetch(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        start_iso = (date.today() + timedelta(days=10)).isoformat()
        end_iso = (date.today() + timedelta(days=5)).isoformat()
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{start_iso}", "endDate": "{end_iso}"}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, reversed dates"
        )

        assert "date" in result.response.lower()
        assert intelligence_use_case.call_count == 0

    async def test_span_beyond_horizon_is_rejected_before_any_fetch(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
            max_forecast_horizon_days=16,
        )
        start_iso = (date.today() + timedelta(days=1)).isoformat()
        end_iso = (date.today() + timedelta(days=40)).isoformat()
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{start_iso}", "endDate": "{end_iso}"}}'
        )

        await orchestrator.process_message(conversation_id=None, user_message="Goa, six weeks")

        assert intelligence_use_case.call_count == 0
        assert attraction_provider.call_count == 0

    async def test_valid_range_proceeds_normally(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        """Regression guard: the validation itself must not block the
        happy path — this is the exact scenario the other tests script."""
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, valid dates"
        )

        assert result.context_complete is True
        assert intelligence_use_case.call_count == 1

    async def test_conversation_still_persists_after_a_rejected_date_range(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        """A rejected range is a conversational turn, not a dead end — the
        user can correct it on the next message."""
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        past_start = (date.today() - timedelta(days=10)).isoformat()
        past_end = (date.today() - timedelta(days=6)).isoformat()
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{past_start}", "endDate": "{past_end}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, last week"
        )

        llm_client.extraction_response = (
            f'{{"startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        second = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="ok how about next month instead"
        )

        assert second.context_complete is True
        assert intelligence_use_case.call_count == 1


class TestStructuredPlaces:
    """Backend gap 1: `ChatResult.places` must carry only real, backend-sourced
    places — never a name Gemini invented — and only what was actually
    fetched this turn."""

    async def test_completing_turn_returns_the_places_the_provider_supplied(
        self, conversation_repo, geocoding, intelligence_use_case, llm_client
    ):
        from tests.application.conftest import FakeAttractionProvider

        attraction_provider = FakeAttractionProvider(
            recommendation=make_attraction_recommendation(start=_START, end=_END)
        )
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None,
            user_message="I'm planning a 4-day trip to Goa from August 20 to August 23",
        )

        names = {place.name for place in result.places}
        assert names == {"Baga Beach", "Museum of Christian Art"}
        # Every place is exactly what the fake provider returned — nothing
        # added, nothing renamed by going through the response pipeline.
        for place in result.places:
            assert place.name in {"Baga Beach", "Museum of Christian Art"}

    async def test_places_are_persisted_on_the_turn_that_fetched_them(
        self, conversation_repo, geocoding, intelligence_use_case, llm_client
    ):
        """Places are trip-level state, not a property of a live response.

        They are computed inside a turn and were previously discarded, so
        reopening a conversation showed no places even though the backend had
        found real ones. Persisting them on the turn's own message is what
        lets a restored thread rebuild the trip workspace.
        """
        from tests.application.conftest import FakeAttractionProvider

        attraction_provider = FakeAttractionProvider(
            recommendation=make_attraction_recommendation(start=_START, end=_END)
        )
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None,
            user_message="I'm planning a trip to Goa",
        )

        assistant = result.conversation.messages[-1]
        persisted = assistant.metadata["places"]
        assert {place["name"] for place in persisted} == {
            "Baga Beach",
            "Museum of Christian Art",
        }
        # Stored in the wire shape the frontend already consumes, so a
        # restored conversation needs no second parser.
        assert set(persisted[0]) == {
            "name",
            "type",
            "latitude",
            "longitude",
            "address",
            "weatherSuitability",
            "reason",
        }

    async def test_turn_without_places_persists_no_places_key(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        """An absent key, never an empty list — "this turn fetched none" and
        "this turn never looked" stay distinguishable to a restoring client."""
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="hello there"
        )

        assert "places" not in result.conversation.messages[-1].metadata

    async def test_places_are_deduplicated_across_days(
        self, conversation_repo, geocoding, intelligence_use_case, llm_client
    ):
        """`make_attraction_recommendation` repeats the same two places on
        every day of the trip — the response must list each place once."""
        from tests.application.conftest import FakeAttractionProvider

        attraction_provider = FakeAttractionProvider(
            recommendation=make_attraction_recommendation(start=_START, end=_END)
        )
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, August 20 to 23"
        )

        assert len(result.places) == 2  # not 2 * (trip length in days)

    async def test_general_chat_turn_returns_no_places(
        self, conversation_repo, geocoding, intelligence_use_case, llm_client
    ):
        from tests.application.conftest import FakeAttractionProvider

        attraction_provider = FakeAttractionProvider(
            recommendation=make_attraction_recommendation(start=_START, end=_END)
        )
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, Aug 20-23"
        )

        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="thanks so much!"
        )

        assert result.intent == ChatIntent.GENERAL_CHAT
        assert result.places == ()

    async def test_places_are_empty_while_context_is_incomplete(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="I want to visit Goa"
        )

        assert result.context_complete is False
        assert result.places == ()


class TestDestinationAmbiguity:
    """Backend gap 3: a chat-resolved destination must never be guessed
    silently when the geocoder returns genuinely different places."""

    async def test_cross_country_match_asks_for_clarification_instead_of_guessing(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"paris": [PARIS_FRANCE, PARIS_TEXAS]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = '{"destination": "Paris"}'

        result = await orchestrator.process_message(
            conversation_id=None, user_message="I'm planning a trip to Paris."
        )

        assert result.context_complete is False
        assert result.conversation.trip_context.destination is None
        assert len(result.destination_candidates) == 2
        assert {c.country for c in result.destination_candidates} == {"France", "United States"}
        assert "Paris" in result.response

    async def test_weather_and_places_are_never_called_before_resolution(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"paris": [PARIS_FRANCE, PARIS_TEXAS]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        await orchestrator.process_message(
            conversation_id=None,
            user_message="Paris, 4 days from August 20 to August 23",
        )

        assert intelligence_use_case.call_count == 0
        assert attraction_provider.call_count == 0
        assert llm_client.chat_call_count == 0

    async def test_conversation_context_is_preserved_across_the_clarification(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        """Dates given in the same message that named an ambiguous
        destination must not be lost while the destination is pending."""
        geocoding = FakeGeocoding(results={"paris": [PARIS_FRANCE, PARIS_TEXAS]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Paris", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Paris, August 20 to 23"
        )

        assert result.conversation.trip_context.start_date == _START
        assert result.conversation.trip_context.end_date == _END
        assert result.conversation.trip_context.destination_query == "Paris"

    async def test_selecting_by_number_resolves_and_continues_the_trip(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"paris": [PARIS_FRANCE, PARIS_TEXAS]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Paris", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Paris, August 20 to 23"
        )
        assert first.destination_candidates  # sanity: the clarification really fired

        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="1"
        )

        assert result.conversation.trip_context.destination == PARIS_FRANCE
        assert result.context_complete is True
        assert intelligence_use_case.call_count == 1
        assert result.destination_candidates == ()

    async def test_selecting_by_country_name_resolves_correctly(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"paris": [PARIS_FRANCE, PARIS_TEXAS]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Paris", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Paris, August 20 to 23"
        )

        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="the one in Texas"
        )

        assert result.conversation.trip_context.destination == PARIS_TEXAS

    async def test_unrecognized_reply_re_asks_with_the_same_candidates(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"paris": [PARIS_FRANCE, PARIS_TEXAS]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Paris", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Paris, August 20 to 23"
        )

        llm_client.extraction_response = "{}"
        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="hmm, not sure"
        )

        assert result.conversation.trip_context.destination is None
        assert len(result.destination_candidates) == 2
        assert intelligence_use_case.call_count == 0

    async def test_same_country_multi_result_still_resolves_automatically(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        """Regression guard: not every multi-result query should trigger a
        clarification — only genuinely different (cross-country) matches."""
        geocoding = FakeGeocoding(results={"springfield": [SPRINGFIELD_MISSOURI]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = '{"destination": "Springfield"}'

        result = await orchestrator.process_message(
            conversation_id=None, user_message="I want to visit Springfield"
        )

        assert result.destination_candidates == ()
        assert result.conversation.trip_context.destination == SPRINGFIELD_MISSOURI

    async def test_a_fresh_ambiguous_mention_clears_a_previously_resolved_destination(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(
            results={"goa": [GOA], "paris": [PARIS_FRANCE, PARIS_TEXAS]}
        )
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Goa, August 20 to 23"
        )
        assert first.conversation.trip_context.destination == GOA

        llm_client.extraction_response = '{"destination": "Paris"}'
        result = await orchestrator.process_message(
            conversation_id=first.conversation.id,
            user_message="actually, let's go to Paris instead",
        )

        assert result.conversation.trip_context.destination is None
        assert len(result.destination_candidates) == 2


class TestContextualUnderstandingScenarios:
    """Section 14's minimum test set — Gemini as the primary understanding
    layer, scripted per scenario via `llm_client.extraction_response` to
    represent what a correctly-functioning extraction call would return.
    These test the *backend's* handling of a given structured extraction
    (validation, TripContext merge, capability selection) — not Gemini's
    own language understanding, which no offline test can verify. See
    "Live test results" in the final report for that half of the picture.
    """

    async def test_1_full_extraction_in_one_turn(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"kerala": [KERALA]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Kerala", "startDate": "{_START_ISO}", '
            f'"endDate": "{_END_ISO}", "interests": ["nature", "food"]}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None,
            user_message=(
                "I'm planning a 4-day trip to Kerala. I love nature and food. "
                "I'll be travelling from September 10 to September 13."
            ),
        )

        assert result.conversation.trip_context.destination == KERALA
        assert result.conversation.trip_context.start_date == _START
        assert result.conversation.trip_context.end_date == _END
        assert set(result.conversation.trip_context.interests) == {"nature", "food"}
        assert result.context_complete is True

    async def test_2_family_context_retained_and_pace_updated(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"kerala": [KERALA]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = '{"destination": "Kerala", "travelStyle": "family"}'
        first = await orchestrator.process_message(
            conversation_id=None, user_message="I'm going to Kerala with my parents."
        )
        assert first.conversation.trip_context.travel_style == "family"

        llm_client.extraction_response = '{"pace": "relaxed"}'
        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="Make it more relaxed."
        )

        assert result.conversation.trip_context.destination == KERALA
        assert result.conversation.trip_context.travel_style == "family"
        assert result.conversation.trip_context.pace == "relaxed"

    async def test_3_destination_retained_across_a_contextual_follow_up(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"goa": [GOA]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="I'm visiting Goa next month."
        )
        assert first.context_complete is True
        attraction_provider.call_count = 0

        llm_client.extraction_response = '{"intent": "recommendation_request"}'
        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="Which day is best for beaches?"
        )

        assert result.conversation.trip_context.destination == GOA
        assert result.intent == ChatIntent.RECOMMENDATION_REQUEST
        assert attraction_provider.call_count == 1

    async def test_4_search_area_does_not_replace_the_trip_destination(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"kerala": [KERALA], "kochi": [KOCHI]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Kerala", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Kerala, planning a trip"
        )
        assert first.context_complete is True

        llm_client.extraction_response = (
            '{"searchArea": "Kochi", "intent": "recommendation_request"}'
        )
        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="Give me more places near Kochi."
        )

        assert result.conversation.trip_context.destination == KERALA
        assert attraction_provider.calls_trip_context[-1].destination == KOCHI

    async def test_5_missing_dates_acknowledged_without_losing_context(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"kerala": [KERALA]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = '{"destination": "Kerala", "travelStyle": "family"}'
        first = await orchestrator.process_message(
            conversation_id=None, user_message="I'm going to Kerala with my parents."
        )
        assert first.context_complete is False

        llm_client.extraction_response = "{}"
        result = await orchestrator.process_message(
            conversation_id=first.conversation.id,
            user_message="I haven't decided the dates yet.",
        )

        assert result.context_complete is False
        assert result.conversation.trip_context.destination == KERALA
        assert "start_date" in result.missing_essentials
        assert result.response  # a natural follow-up, not a dead end

    async def test_6_weather_conditional_question_is_weather_aware(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"kerala": [KERALA]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Kerala", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Kerala, planning a trip"
        )
        intelligence_use_case.call_count = 0
        attraction_provider.call_count = 0

        llm_client.extraction_response = '{"intent": "weather_question"}'
        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="What if it rains?"
        )

        assert result.intent == ChatIntent.WEATHER_QUESTION
        assert intelligence_use_case.call_count == 1
        assert attraction_provider.call_count == 1
        assert result.conversation.trip_context.destination == KERALA

    async def test_7_changing_destination_replaces_the_old_one(
        self, conversation_repo, intelligence_use_case, attraction_provider, llm_client
    ):
        geocoding = FakeGeocoding(results={"kerala": [KERALA], "bangalore": [BANGALORE]})
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Kerala", "startDate": "{_START_ISO}", "endDate": "{_END_ISO}"}}'
        )
        first = await orchestrator.process_message(
            conversation_id=None, user_message="Kerala, planning a trip"
        )
        assert first.conversation.trip_context.destination == KERALA

        llm_client.extraction_response = '{"destination": "Bangalore"}'
        result = await orchestrator.process_message(
            conversation_id=first.conversation.id, user_message="Change the trip to Bangalore."
        )

        assert result.conversation.trip_context.destination == BANGALORE
        assert result.conversation.trip_context.destination != KERALA


class TestDurationNormalization:
    """Backend normalization, not something Gemini is asked to compute: a
    stated trip length fills in the end date when a start date is known and
    no explicit end date was extracted."""

    async def test_duration_fills_in_the_end_date(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", "duration": 4}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="4-day trip to Goa starting August 20"
        )

        assert result.conversation.trip_context.end_date == _START + timedelta(days=3)
        assert result.context_complete is True

    async def test_duration_is_ignored_when_an_explicit_end_date_is_also_given(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        """The explicit date always wins — duration only fills a genuine gap."""
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = (
            f'{{"destination": "Goa", "startDate": "{_START_ISO}", '
            f'"endDate": "{_END_ISO}", "duration": 30}}'
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="Goa trip"
        )

        assert result.conversation.trip_context.end_date == _END

    async def test_duration_without_a_start_date_does_nothing(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )
        llm_client.extraction_response = '{"destination": "Goa", "duration": 4}'

        result = await orchestrator.process_message(
            conversation_id=None, user_message="4-day trip to Goa"
        )

        assert result.conversation.trip_context.end_date is None
        assert result.context_complete is False


class TestMalformedExtractionResponse:
    """A syntactically valid JSON response that isn't an object (a bare
    array, string, or number) must be treated the same as a call failure —
    never silently propagated as "nothing extracted" from a technically
    successful call."""

    async def test_non_object_json_falls_back_to_heuristic(
        self, conversation_repo, geocoding, intelligence_use_case, attraction_provider, llm_client
    ):
        llm_client.extraction_response = '["Goa", "August"]'

        orchestrator = make_orchestrator(
            conversation_repo=conversation_repo,
            geocoding=geocoding,
            intelligence_use_case=intelligence_use_case,
            attraction_provider=attraction_provider,
            llm_client=llm_client,
        )

        result = await orchestrator.process_message(
            conversation_id=None, user_message="I want to visit Goa"
        )

        # The fallback heuristic still finds "Goa" from the raw message.
        assert result.conversation.trip_context.destination == GOA
