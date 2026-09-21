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
    """Answer identically on every configured host.

    `_INTERPRETER_URLS` may list more than one host, so a test that only
    mocked the first would let a failure case escape to the real network
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


class TestStaysAndSportsCategories:
    """Real OSM tag mappings for stays (hotel/guest_house) and sports
    facilities — same pipeline as every other category, no new provider
    logic."""

    @respx.mock
    async def test_hotel_and_guest_house_map_to_their_categories(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        hotel = {
            "type": "node",
            "id": 501,
            "lat": 15.31,
            "lon": 74.13,
            "tags": {"name": "Seaside Hotel", "tourism": "hotel"},
        }
        guest_house = {
            "type": "node",
            "id": 502,
            "lat": 15.32,
            "lon": 74.14,
            "tags": {"name": "Backpacker Hostel", "tourism": "hostel"},
        }
        _mock({"elements": [hotel, guest_house]})

        places = await adapter.search(
            latitude=15.3,
            longitude=74.1,
            categories=(AttractionType.HOTEL, AttractionType.GUEST_HOUSE),
        )

        by_name = {p.name: p.category for p in places}
        assert by_name["Seaside Hotel"] == AttractionType.HOTEL
        assert by_name["Backpacker Hostel"] == AttractionType.GUEST_HOUSE

    @respx.mock
    async def test_sports_facility_tags_map_to_sports_facility(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        pitch = {
            "type": "way",
            "id": 503,
            "center": {"lat": 15.33, "lon": 74.15},
            "tags": {"name": "Town Sports Centre", "leisure": "sports_centre"},
        }
        _mock({"elements": [pitch]})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.SPORTS_FACILITY,)
        )

        assert len(places) == 1
        assert places[0].category == AttractionType.SPORTS_FACILITY

    @respx.mock
    async def test_broadened_food_tags_are_recognized(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        fast_food = {
            "type": "node",
            "id": 504,
            "lat": 15.34,
            "lon": 74.16,
            "tags": {"name": "Quick Bites", "amenity": "fast_food"},
        }
        bakery = {
            "type": "node",
            "id": 505,
            "lat": 15.35,
            "lon": 74.17,
            "tags": {"name": "Corner Bakery", "shop": "bakery"},
        }
        _mock({"elements": [fast_food, bakery]})

        places = await adapter.search(
            latitude=15.3, longitude=74.1, categories=(AttractionType.FOOD,)
        )

        assert {p.name for p in places} == {"Quick Bites", "Corner Bakery"}


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
            "tags": {"name": "Somewhere", "amenity": "parking"},
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


class TestCategoryFairness:
    """Live-observed regression: a multi-category request ("viewpoints,
    cafes, beaches, monuments, restaurants") came back as restaurants only.
    The category-matching itself was correct — the bug was one shared
    `out center N` after every tag clause was unioned together, which let
    an abundant category (restaurants, sorted first alphabetically) fill
    the entire cap before a sparser clause (viewpoint, beach) ever
    contributed a result."""

    def test_each_tag_gets_its_own_out_statement(self) -> None:
        query = overpass._build_query(
            latitude=15.3,
            longitude=74.1,
            radius_m=15_000,
            tag_pairs={("amenity", "restaurant"), ("tourism", "viewpoint"), ("natural", "beach")},
            limit=30,
        )

        # One `nwr` immediately followed by its own `out` per tag — not a
        # single unioned block with one shared `out` at the end.
        assert query.count("out center") == 3
        tags = [("amenity", "restaurant"), ("tourism", "viewpoint"), ("natural", "beach")]
        for key, value in tags:
            nwr_index = query.index(f'nwr["{key}"="{value}"]')
            next_out_index = query.index("out center", nwr_index)
            # No other nwr clause sits between this one and its own `out`.
            assert "nwr[" not in query[nwr_index + 1 : next_out_index]

    def test_per_tag_share_never_collapses_to_zero_with_many_categories(self) -> None:
        query = overpass._build_query(
            latitude=15.3,
            longitude=74.1,
            radius_m=15_000,
            tag_pairs={
                ("amenity", "restaurant"), ("tourism", "viewpoint"), ("natural", "beach"),
                ("historic", "monument"), ("tourism", "museum"), ("tourism", "attraction"),
                ("leisure", "park"), ("tourism", "hotel"), ("amenity", "cafe"),
                ("leisure", "sports_centre"),
            },
            limit=20,  # fewer than the 10 categories requested
        )

        assert "out center 0" not in query
        assert overpass._MIN_RESULTS_PER_TAG > 0
        assert f"out center {overpass._MIN_RESULTS_PER_TAG}" in query

    @respx.mock
    async def test_a_sparse_category_is_not_crowded_out_by_an_abundant_one(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        """Overpass itself enforces the per-statement `out` cap (not
        something this test can simulate through a mock), so this checks
        the layer this codebase controls: parsing correctly keeps every
        element Overpass actually returns, across every requested category,
        with no additional truncation on top."""
        restaurants = [
            {
                "type": "node",
                "id": 1000 + i,
                "lat": 15.3 + i * 0.001,
                "lon": 74.1,
                "tags": {"name": f"Restaurant {i}", "amenity": "restaurant"},
            }
            for i in range(30)
        ]
        viewpoint = {
            "type": "node",
            "id": 2000,
            "lat": 15.31,
            "lon": 74.11,
            "tags": {"name": "Fort Aguada Viewpoint", "tourism": "viewpoint"},
        }
        _mock({"elements": [*restaurants, viewpoint]})

        places = await adapter.search(
            latitude=15.3,
            longitude=74.1,
            categories=(AttractionType.RESTAURANT, AttractionType.VIEWPOINT),
        )

        names = {p.name for p in places}
        assert "Fort Aguada Viewpoint" in names
        assert len(names) == 31


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


class TestSingleHost:
    """Only one Overpass host is configured (the former second host,
    `overpass.kumi.systems`, was removed — measured dead, and it never once
    rescued a request in production; see the comment on `_INTERPRETER_URLS`).
    The fallback loop itself remains, so a primary failure is still a clean
    `PlacesUnavailableError`, not an unhandled exception."""

    @respx.mock
    async def test_only_one_host_is_configured(self) -> None:
        assert len(overpass._INTERPRETER_URLS) == 1

    @respx.mock
    async def test_primary_failure_raises_places_unavailable_with_no_fallback(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        primary = respx.post(overpass._INTERPRETER_URLS[0]).mock(
            return_value=httpx.Response(504, text="gateway timeout")
        )

        with pytest.raises(PlacesUnavailableError):
            await adapter.search(latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,))

        assert primary.called

    @respx.mock
    async def test_unexpected_elements_shape_raises_places_unavailable(
        self, adapter: OverpassPlacesProvider
    ) -> None:
        _mock({"elements": "not-a-list"})

        with pytest.raises(PlacesUnavailableError):
            await adapter.search(latitude=15.3, longitude=74.1, categories=(AttractionType.BEACH,))
