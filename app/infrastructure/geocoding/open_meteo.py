"""Open-Meteo geocoding adapter: place name -> coordinates.

Keyless, like the Open-Meteo *forecast* adapter — resolving a destination adds
no second credential to protect, which is why this provider is preferred over
the keyed alternatives (FDS §17.1 makes the same argument for the browser-side
lookup this mirrors).

Reuses `providers.base.call_with_retry` rather than rolling its own `httpx` +
`tenacity` setup, so geocoding inherits exactly the timeout and
retry-only-on-transient policy every weather adapter already follows.
"""

import unicodedata
from functools import lru_cache
from typing import Any

import httpx

from app.domain.entities.trip import GeocodedPlace
from app.domain.ports.geocoding import (
    DEFAULT_SEARCH_LIMIT,
    GeocodingPort,
    GeocodingUnavailableError,
)
from app.infrastructure.config.settings import Settings, get_settings
from app.infrastructure.providers.base import ProviderError, build_http_client, call_with_retry

_BASE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def _fold(value: str) -> str:
    """Case- and diacritic-insensitive form, for comparing a query to a name."""
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.casefold().strip()


def _rank_by_exactness(places: list[GeocodedPlace], query: str) -> list[GeocodedPlace]:
    """Promote exact name matches above fuzzy ones.

    Open-Meteo's search is fuzzy and ranks by population, so a bare "Goa"
    returns *Genoa, Italy* first. For a dashboard that only ever offered a
    disambiguation list this was cosmetic; for a chat assistant that resolves
    a destination on the user's behalf it is a correctness problem — the
    assistant would silently plan a trip to the wrong country.

    A stable partition, not a re-sort: exact matches keep their relative
    order and so does everything else, so the provider's population ranking
    still breaks ties between two places genuinely named the same.
    """
    target = _fold(query.split(",")[0])
    if not target:
        return places

    exact = [place for place in places if _fold(place.name) == target]
    rest = [place for place in places if _fold(place.name) != target]
    return exact + rest


def _to_place(raw: dict[str, Any]) -> GeocodedPlace | None:
    """Map one provider result, or `None` if it is unusable.

    A result without a name or coordinates is dropped rather than defaulted —
    the same "missing stays missing" rule the weather adapters follow, because
    a fabricated coordinate here would send a whole trip somewhere real but
    wrong.
    """
    name = raw.get("name")
    latitude = raw.get("latitude")
    longitude = raw.get("longitude")
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(latitude, int | float) or not isinstance(longitude, int | float):
        return None
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        return None

    # `admin2` adds the district that separates same-named places inside one
    # region — the "Goa, Camarines Sur" case disambiguation exists for.
    region = ", ".join(
        part for part in (raw.get("admin1"), raw.get("admin2")) if isinstance(part, str) and part
    )

    return GeocodedPlace(
        name=name.strip(),
        latitude=float(latitude),
        longitude=float(longitude),
        country=_optional_str(raw.get("country")),
        country_code=_optional_str(raw.get("country_code")),
        admin1=region or None,
        timezone=_optional_str(raw.get("timezone")),
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


class OpenMeteoGeocoding(GeocodingPort):
    """`GeocodingPort` backed by Open-Meteo's keyless geocoding API."""

    name = "open_meteo_geocoding"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        retry_attempts: int,
        retry_backoff_seconds: float,
    ) -> None:
        self._client = client
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    async def search(
        self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> list[GeocodedPlace]:
        trimmed = query.strip()
        if not trimmed:
            return []

        places = await self._search_once(trimmed, limit)
        if places or "," in trimmed:
            # A comma already separates the specific place from its region
            # ("Varkala, Kerala") and Open-Meteo handles that shape natively
            # — confirmed live: it returns Varkala either way. Only a bare
            # space-separated miss needs the word-dropping fallback below.
            return _rank_by_exactness(places, trimmed)

        # Live-observed failure: "varkala kerala" (no comma) returns zero
        # results from Open-Meteo even though "varkala" alone matches
        # perfectly — its name search wants a single place name, not a
        # "place + region" phrase without a separator. This is exactly how
        # people naturally say a destination in conversation, so the
        # extraction step cannot be relied on to always add the comma
        # itself. Retry with the phrase trimmed one trailing word at a time
        # — most specific first — rather than collapsing straight to the
        # first word, which would risk matching the wrong place for a
        # genuinely multi-word name ("Fort Kochi Kerala" should try "Fort
        # Kochi" before "Fort").
        words = trimmed.split()
        for cut in range(len(words) - 1, 0, -1):
            candidate = " ".join(words[:cut])
            places = await self._search_once(candidate, limit)
            if places:
                return _rank_by_exactness(places, candidate)

        return []

    async def _search_once(self, name: str, limit: int) -> list[GeocodedPlace]:
        params: dict[str, str | int] = {
            "name": name,
            "count": limit,
            "language": "en",
            "format": "json",
        }

        async def _request() -> httpx.Response:
            response = await self._client.get(_BASE_URL, params=params)
            response.raise_for_status()
            return response

        try:
            response = await call_with_retry(
                _request,
                provider=self.name,
                attempts=self._retry_attempts,
                backoff_seconds=self._retry_backoff_seconds,
            )
        except ProviderError as exc:
            # Covers ProviderTimeoutError too — it subclasses ProviderError.
            raise GeocodingUnavailableError(str(exc)) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise GeocodingUnavailableError(f"[{self.name}] malformed JSON response") from exc

        if not isinstance(payload, dict):
            raise GeocodingUnavailableError(f"[{self.name}] unexpected response shape")

        # Open-Meteo omits `results` entirely when nothing matches, rather than
        # returning an empty list — so a missing key is "no match", not an error.
        results = payload.get("results") or []
        if not isinstance(results, list):
            raise GeocodingUnavailableError(f"[{self.name}] unexpected 'results' shape")

        return [
            place
            for place in (_to_place(raw) for raw in results if isinstance(raw, dict))
            if place is not None
        ]

    async def aclose(self) -> None:
        """Close the HTTP client this adapter was constructed with."""
        await self._client.aclose()


def build_geocoding_service(settings: Settings, client: httpx.AsyncClient) -> OpenMeteoGeocoding:
    """Wire the adapter from Phase 2 settings, sharing the provider retry policy."""
    return OpenMeteoGeocoding(
        client,
        retry_attempts=settings.provider_retry_attempts,
        retry_backoff_seconds=settings.provider_retry_backoff_seconds,
    )


@lru_cache
def get_geocoding_service() -> OpenMeteoGeocoding:
    """Return the process-wide geocoding adapter, constructed on first call.

    Its own client, not the provider registry's: a geocoding outage and a
    weather outage are independent failures, and sharing a pool would let one
    exhaust the other.
    """
    settings = get_settings()
    client = build_http_client(settings.provider_timeout_seconds)
    return build_geocoding_service(settings, client)
