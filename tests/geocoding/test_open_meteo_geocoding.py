"""Open-Meteo geocoding adapter — offline via respx.

Covers the three things that decide whether a chat assistant sends someone to
the right country: exact-match promotion, malformed results being dropped
rather than defaulted, and "no match" being an empty answer rather than an
error.
"""

import httpx
import pytest
import respx

from app.domain.ports.geocoding import GeocodingUnavailableError
from app.infrastructure.geocoding import open_meteo
from app.infrastructure.geocoding.open_meteo import OpenMeteoGeocoding

_GOA_INDIA = {
    "id": 1,
    "name": "Goa",
    "latitude": 15.29927,
    "longitude": 74.12401,
    "country": "India",
    "country_code": "IN",
    "admin1": "Goa",
    "timezone": "Asia/Kolkata",
}
_GENOA = {
    "id": 2,
    "name": "Genoa",
    "latitude": 44.4056,
    "longitude": 8.9463,
    "country": "Italy",
    "country_code": "IT",
    "admin1": "Liguria",
    "timezone": "Europe/Rome",
}


@pytest.fixture
def adapter() -> OpenMeteoGeocoding:
    return OpenMeteoGeocoding(
        httpx.AsyncClient(), retry_attempts=2, retry_backoff_seconds=0.01
    )


def _mock(payload: object, status: int = 200) -> None:
    respx.get(open_meteo._BASE_URL).mock(return_value=httpx.Response(status, json=payload))


class TestSearch:
    @respx.mock
    async def test_maps_provider_result_to_geocoded_place(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        _mock({"results": [_GOA_INDIA]})

        places = await adapter.search("Goa")

        assert len(places) == 1
        place = places[0]
        assert place.name == "Goa"
        assert place.latitude == pytest.approx(15.29927)
        assert place.longitude == pytest.approx(74.12401)
        assert place.country == "India"
        assert place.country_code == "IN"
        assert place.timezone == "Asia/Kolkata"

    @respx.mock
    async def test_location_id_matches_the_backend_coordinate_format(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        """The id must be directly usable as `locations/{id}` on the weather API."""
        _mock({"results": [_GOA_INDIA]})

        place = (await adapter.search("Goa"))[0]

        assert place.location_id == "15.2993,74.1240"

    @respx.mock
    async def test_admin1_and_admin2_are_combined_for_disambiguation(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        _mock({"results": [{**_GOA_INDIA, "admin1": "Bicol", "admin2": "Camarines Sur"}]})

        place = (await adapter.search("Goa"))[0]

        assert place.admin1 == "Bicol, Camarines Sur"


class TestExactnessRanking:
    """Open-Meteo ranks by population, so a bare "Goa" returns Genoa first."""

    @respx.mock
    async def test_exact_name_match_is_promoted_above_fuzzy_match(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        _mock({"results": [_GENOA, _GOA_INDIA]})

        places = await adapter.search("Goa")

        assert [place.name for place in places] == ["Goa", "Genoa"]

    @respx.mock
    async def test_ranking_is_case_and_diacritic_insensitive(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        malaga = {**_GENOA, "name": "Málaga", "country": "Spain"}
        _mock({"results": [_GENOA, malaga]})

        places = await adapter.search("MALAGA")

        assert places[0].name == "Málaga"

    @respx.mock
    async def test_only_the_name_segment_of_a_query_is_matched(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        """A user may type "Goa, India"; only "Goa" is the place name."""
        _mock({"results": [_GENOA, _GOA_INDIA]})

        places = await adapter.search("Goa, India")

        assert places[0].name == "Goa"

    @respx.mock
    async def test_non_matching_results_keep_provider_order(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        """A stable partition, not a re-sort: population ranking still applies."""
        _mock({"results": [_GENOA, _GOA_INDIA]})

        places = await adapter.search("nowhere-in-particular")

        assert [place.name for place in places] == ["Genoa", "Goa"]


class TestNoMatch:
    @respx.mock
    async def test_missing_results_key_returns_empty_not_error(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        """Open-Meteo omits `results` entirely when nothing matches."""
        _mock({"generationtime_ms": 0.1})

        assert await adapter.search("zzzzzzzz") == []

    @respx.mock
    async def test_null_results_returns_empty(self, adapter: OpenMeteoGeocoding) -> None:
        _mock({"results": None})

        assert await adapter.search("zzzzzzzz") == []

    async def test_blank_query_makes_no_request(self, adapter: OpenMeteoGeocoding) -> None:
        with respx.mock:
            route = respx.get(open_meteo._BASE_URL)
            assert await adapter.search("   ") == []
            assert not route.called


class TestMalformedResults:
    @respx.mock
    async def test_result_without_coordinates_is_dropped_not_defaulted(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        _mock({"results": [{"name": "Nowhere"}, _GOA_INDIA]})

        places = await adapter.search("Goa")

        assert [place.name for place in places] == ["Goa"]

    @respx.mock
    async def test_result_without_a_name_is_dropped(self, adapter: OpenMeteoGeocoding) -> None:
        _mock({"results": [{"latitude": 1.0, "longitude": 2.0}, _GOA_INDIA]})

        places = await adapter.search("Goa")

        assert [place.name for place in places] == ["Goa"]

    @respx.mock
    async def test_non_dict_entries_are_ignored(self, adapter: OpenMeteoGeocoding) -> None:
        _mock({"results": ["nonsense", 42, _GOA_INDIA]})

        places = await adapter.search("Goa")

        assert [place.name for place in places] == ["Goa"]

    @respx.mock
    async def test_optional_fields_absent_become_none(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        _mock({"results": [{"name": "Goa", "latitude": 15.3, "longitude": 74.1}]})

        place = (await adapter.search("Goa"))[0]

        assert place.country is None
        assert place.country_code is None
        assert place.admin1 is None
        assert place.timezone is None


class TestProviderFailure:
    @respx.mock
    async def test_server_error_raises_geocoding_unavailable(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        _mock({"error": True}, status=500)

        with pytest.raises(GeocodingUnavailableError):
            await adapter.search("Goa")

    @respx.mock
    async def test_client_error_raises_geocoding_unavailable(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        _mock({"error": True}, status=400)

        with pytest.raises(GeocodingUnavailableError):
            await adapter.search("Goa")

    @respx.mock
    async def test_timeout_raises_geocoding_unavailable(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        respx.get(open_meteo._BASE_URL).mock(side_effect=httpx.TimeoutException("slow"))

        with pytest.raises(GeocodingUnavailableError):
            await adapter.search("Goa")

    @respx.mock
    async def test_malformed_json_raises_geocoding_unavailable(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        respx.get(open_meteo._BASE_URL).mock(
            return_value=httpx.Response(200, content=b"not json")
        )

        with pytest.raises(GeocodingUnavailableError):
            await adapter.search("Goa")

    @respx.mock
    async def test_unexpected_payload_shape_raises_geocoding_unavailable(
        self, adapter: OpenMeteoGeocoding
    ) -> None:
        _mock(["unexpected", "list"])

        with pytest.raises(GeocodingUnavailableError):
            await adapter.search("Goa")
