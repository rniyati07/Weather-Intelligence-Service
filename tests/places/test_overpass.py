"""Overpass places adapter — offline via respx.

Covers the required areas: successful response, empty results, provider
failure, category mapping, malformed provider data — mirroring
`tests/geocoding/test_open_meteo_geocoding.py`'s structure.
"""

import httpx
import pytest
import respx

from app.domain.entities.attractions import AttractionType
from app.domain.ports.places import PlacesUnavailableError
from app.infrastructure.places import overpass
from app.infrastructure.places.overpass import OverpassPlacesProvider

_BEACH_NODE = {
    "type": "node",
    "id": 111,
    "lat": 15.5439,
    "lon": 73.7553,
    "tags": {"name": "Calangute Beach", "natural": "beach"},
}
_MUSEUM_WAY = {
    "type": "way",
    "id": 222,
    "center": {"lat": 15.4989, "lon": 73.8278},
    "tags": {
        "name": "Museum of Christian Art",
        "tourism": "museum",
        "addr:street": "Rua de Ourem",
        "addr:city": "Goa",
    },
}


@pytest.fixture
def adapter() -> OverpassPlacesProvider:
    return OverpassPlacesProvider(httpx.AsyncClient(), retry_attempts=2, retry_backoff_seconds=0.01)


def _mock(payload: object, status: int = 200) -> None:
    """Answer identically on every host.

    The adapter falls through its mirror list on failure, so a test that only
    mocked the primary would let a failure case escape to the real network
    instead of asserting on the adapter.
    """
    for url in overpass._INTERPRETER_URLS:
        respx.post(url).mock(return_value=httpx.Response(status, json=payload))


class TestSearch:
    @respx.mock
    async def test_maps_node_and_way_to_raw_place(self, adapter: OverpassPlacesProvider) -> None:
        _mock({"elements": [_BEACH_NODE, _MUSEUM_WAY]})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH, AttractionType.MUSEUM)
        )

        assert len(places) == 2
        beach = next(p for p in places if p.name == "Calangute Beach")
        assert beach.category == AttractionType.BEACH
        assert beach.latitude == pytest.approx(15.5439)
        assert beach.source_id == "node/111"

        museum = next(p for p in places if p.name == "Museum of Christian Art")
        assert museum.category == AttractionType.MUSEUM
        assert museum.latitude == pytest.approx(15.4989)  # from `center`, not lat/lon
        assert museum.address == "Rua de Ourem, Goa"

    @respx.mock
    async def test_no_categories_makes_no_request(self, adapter: OverpassPlacesProvider) -> None:
        route = respx.post(overpass._INTERPRETER_URLS[0])
        places = await adapter.search(latitude=15.3, longitude=74.1, categories=())
        assert places == []
        assert not route.called

    @respx.mock
    async def test_empty_elements_returns_empty_not_error(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        _mock({"elements": []})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,)
        )

        assert places == []

    @respx.mock
    async def test_duplicate_elements_are_deduplicated_by_source_id(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        _mock({"elements": [_BEACH_NODE, _BEACH_NODE]})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,)
        )

        assert len(places) == 1


class TestMalformedElements:
    @respx.mock
    async def test_element_without_name_is_dropped(self, adapter: OverpassPlacesProvider) -> None:
        unnamed = {"type": "node", "id": 999, "lat": 1.0, "lon": 2.0, "tags": {"natural": "beach"}}
        _mock({"elements": [unnamed, _BEACH_NODE]})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,)
        )

        assert [p.name for p in places] == ["Calangute Beach"]

    @respx.mock
    async def test_element_with_unmapped_tags_is_dropped(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        unmapped = {
            "type": "node",
            "id": 333,
            "lat": 1.0,
            "lon": 2.0,
            "tags": {"name": "Somewhere", "shop": "bakery"},
        }
        _mock({"elements": [unmapped, _BEACH_NODE]})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,)
        )

        assert [p.name for p in places] == ["Calangute Beach"]

    @respx.mock
    async def test_way_without_center_is_dropped(self, adapter: OverpassPlacesProvider) -> None:
        broken_way = {
            "type": "way",
            "id": 444,
            "tags": {"name": "Ghost Museum", "tourism": "museum"},
        }
        _mock({"elements": [broken_way, _BEACH_NODE]})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,)
        )

        assert [p.name for p in places] == ["Calangute Beach"]

    @respx.mock
    async def test_non_dict_elements_are_ignored(self, adapter: OverpassPlacesProvider) -> None:
        _mock({"elements": ["nonsense", 42, _BEACH_NODE]})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,)
        )

        assert [p.name for p in places] == ["Calangute Beach"]


class TestProviderFailure:
    @respx.mock
    async def test_server_error_raises_places_unavailable(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        _mock({"error": True}, status=500)

        with pytest.raises(PlacesUnavailableError):
            await adapter.search(latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,))

    @respx.mock
    async def test_timeout_raises_places_unavailable(self, adapter: OverpassPlacesProvider) -> None:
        for url in overpass._INTERPRETER_URLS:
            respx.post(url).mock(side_effect=httpx.TimeoutException("slow"))

        with pytest.raises(PlacesUnavailableError):
            await adapter.search(latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,))

    @respx.mock
    async def test_malformed_json_raises_places_unavailable(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        respx.post(overpass._INTERPRETER_URLS[0]).mock(
            return_value=httpx.Response(200, content=b"not json")
        )

        with pytest.raises(PlacesUnavailableError):
            await adapter.search(latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,))


class TestHostFallback:
    """A public Overpass instance intermittently answers a valid query with
    `504`. Retrying the same overloaded host does not help, so the adapter
    falls through to a mirror — without it, a trip loses its places for a
    reason that has nothing to do with the data."""

    @respx.mock
    async def test_falls_through_to_the_mirror_when_the_primary_fails(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        primary = respx.post(overpass._INTERPRETER_URLS[0]).mock(
            return_value=httpx.Response(504, text="gateway timeout")
        )
        mirror = respx.post(overpass._INTERPRETER_URLS[1]).mock(
            return_value=httpx.Response(200, json={"elements": [_BEACH_NODE]})
        )

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,)
        )

        assert [place.name for place in places] == ["Calangute Beach"]
        assert primary.called
        assert mirror.called

    @respx.mock
    async def test_does_not_call_the_mirror_when_the_primary_answers(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        respx.post(overpass._INTERPRETER_URLS[0]).mock(
            return_value=httpx.Response(200, json={"elements": [_BEACH_NODE]})
        )
        mirror = respx.post(overpass._INTERPRETER_URLS[1])

        await adapter.search(latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,))

        assert not mirror.called

    @respx.mock
    async def test_unexpected_elements_shape_raises_places_unavailable(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        _mock({"elements": "not-a-list"})

        with pytest.raises(PlacesUnavailableError):
            await adapter.search(latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,))
