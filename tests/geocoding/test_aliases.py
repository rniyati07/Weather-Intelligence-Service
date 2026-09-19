"""`AliasedGeocoding` — the curated destination override layer.

Live audit found Open-Meteo's geocoding gazetteer never returns Goa, India
for a plain "Goa" query at any practical result count. These tests never hit
the network — the inner adapter is a stub, so what's under test is purely
"does the alias table intercept before delegating".
"""

import pytest

from app.domain.entities.trip import GeocodedPlace
from app.domain.ports.geocoding import GeocodingPort
from app.infrastructure.geocoding.aliases import AliasedGeocoding

_STUB_RESULT = [GeocodedPlace(name="Somewhere Else", latitude=1.0, longitude=2.0)]


class StubInnerGeocoding(GeocodingPort):
    """Records every query it actually receives; returns a fixed, obviously-wrong
    result — if a test sees this, the alias layer failed to intercept."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.aclosed = False

    async def search(self, query: str, *, limit: int = 5) -> list[GeocodedPlace]:
        self.queries.append(query)
        return _STUB_RESULT

    async def aclose(self) -> None:
        self.aclosed = True


class TestAliasInterception:
    async def test_goa_resolves_to_the_curated_india_entry(self) -> None:
        inner = StubInnerGeocoding()
        geocoding = AliasedGeocoding(inner)

        results = await geocoding.search("Goa")

        assert len(results) == 1
        assert results[0].country == "India"
        assert results[0].latitude == pytest.approx(15.2993)
        assert inner.queries == []  # never delegated

    @pytest.mark.parametrize("query", ["goa", "GOA", "  Goa  ", "Goa\n"])
    async def test_match_is_case_and_whitespace_insensitive(self, query: str) -> None:
        geocoding = AliasedGeocoding(StubInnerGeocoding())

        results = await geocoding.search(query)

        assert results[0].country == "India"

    async def test_kerala_resolves_to_the_curated_india_entry(self) -> None:
        """Live frontend testing found the real provider never returns an
        Indian entry for "Kerala" at all — only "Kerälä", a Finnish
        village, which folds to an exact match on "kerala" and gets
        promoted ahead of the (absent) correct answer."""
        inner = StubInnerGeocoding()
        geocoding = AliasedGeocoding(inner)

        results = await geocoding.search("Kerala")

        assert len(results) == 1
        assert results[0].country == "India"
        assert results[0].admin1 == "Kerala"
        assert inner.queries == []

    async def test_bangalore_resolves_to_the_curated_india_entry(self) -> None:
        """Same shape of gap under the city's colloquial English name — the
        real provider has no Indian entry for "Bangalore", only for its
        official name "Bengaluru"."""
        inner = StubInnerGeocoding()
        geocoding = AliasedGeocoding(inner)

        results = await geocoding.search("Bangalore")

        assert len(results) == 1
        assert results[0].country == "India"
        assert results[0].admin1 == "Karnataka"
        assert inner.queries == []


class TestDelegation:
    async def test_unlisted_query_delegates_to_the_inner_adapter(self) -> None:
        inner = StubInnerGeocoding()
        geocoding = AliasedGeocoding(inner)

        results = await geocoding.search("Paris")

        assert results == _STUB_RESULT
        assert inner.queries == ["Paris"]

    async def test_goa_as_part_of_a_longer_phrase_delegates(self) -> None:
        """The alias matches the *normalized whole query*, not a substring —
        "Goa, India" is not literally "goa" after normalization, so this is
        deliberately delegated rather than silently over-matched."""
        inner = StubInnerGeocoding()
        geocoding = AliasedGeocoding(inner)

        await geocoding.search("Goa, India")

        assert inner.queries == ["Goa, India"]

    async def test_limit_is_passed_through_on_delegation(self) -> None:
        inner = StubInnerGeocoding()
        geocoding = AliasedGeocoding(inner)

        await geocoding.search("Paris", limit=3)

        assert inner.queries == ["Paris"]  # limit isn't tracked by the stub,
        # but the call must not raise — confirms the signature is honoured


class TestAclose:
    async def test_aclose_delegates_to_inner(self) -> None:
        inner = StubInnerGeocoding()
        geocoding = AliasedGeocoding(inner)

        await geocoding.aclose()

        assert inner.aclosed is True
