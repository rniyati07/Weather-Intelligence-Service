"""Overpass (OpenStreetMap) places adapter.

Keyless, per the approved decision — matches the same "no second secret"
reasoning already applied to Open-Meteo weather and geocoding. Bounded
`around:` queries only; this module never issues an unbounded regional query.

Reuses `providers.base.call_with_retry` and the generic `PROVIDER_*` settings
(timeout, retry attempts, backoff) rather than adding Overpass-specific
config — those settings were never weather-specific in name, only in current
usage.
"""

import logging
from functools import lru_cache
from typing import Any

import httpx

from app.domain.entities.attractions import AttractionType
from app.domain.entities.place import RawPlace
from app.domain.ports.places import (
    DEFAULT_RESULT_LIMIT,
    DEFAULT_SEARCH_RADIUS_M,
    PlacesPort,
    PlacesUnavailableError,
)
from app.infrastructure.config.settings import Settings, get_settings
from app.infrastructure.providers.base import ProviderError, build_http_client, call_with_retry

logger = logging.getLogger(__name__)

#: Public Overpass instances, tried in order.
#:
#: The main instance intermittently answers a perfectly valid query with
#: `504 Gateway Timeout` under load. `call_with_retry` alone does not help:
#: it retries the *same* overloaded host, so a trip could end up with no
#: places at all while the data itself was fine. Falling through to a mirror
#: is what makes places reliable in practice — same query, same parsing, and
#: the first host that answers wins.
_INTERPRETER_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

#: Overpass's own execution budget, embedded in the query itself.
#:
#: Kept at or below the client's own timeout on purpose. Asking the server for
#: a 25s budget while the client gives up at `PROVIDER_TIMEOUT_SECONDS` (5s)
#: meant a heavier multi-tag query — the kind a trip with several interests
#: produces — was still being computed server-side long after we had stopped
#: waiting, so it surfaced as "no places for this trip" rather than as a
#: timeout anyone could see. Overpass also schedules a query against the
#: budget it is given, so a smaller one is admitted sooner.
_QUERY_TIMEOUT_SECONDS = 20

#: `AttractionType` -> the OSM `(key, value)` tag pairs that identify it.
#: Deliberately approximate — OSM tagging is inconsistent worldwide, and a
#: best-effort mapping that sometimes over-matches (e.g. `INDOOR_ACTIVITY`
#: overlapping `MUSEUM`) is preferable to an empty result for categories with
#: no single canonical tag. Overlap is harmless: results are deduplicated by
#: OSM id before ranking.
_CATEGORY_TAGS: dict[AttractionType, tuple[tuple[str, str], ...]] = {
    AttractionType.BEACH: (("natural", "beach"),),
    AttractionType.MUSEUM: (("tourism", "museum"),),
    AttractionType.LANDMARK: (("tourism", "attraction"),),
    AttractionType.VIEWPOINT: (("tourism", "viewpoint"),),
    AttractionType.RESTAURANT: (("amenity", "restaurant"),),
    AttractionType.CULTURAL_SITE: (("tourism", "gallery"), ("historic", "monument")),
    AttractionType.OUTDOOR_ACTIVITY: (("leisure", "park"),),
    AttractionType.INDOOR_ACTIVITY: (("tourism", "museum"), ("leisure", "fitness_centre")),
    AttractionType.NATURE: (("leisure", "park"), ("natural", "wood")),
    AttractionType.SHOPPING: (("shop", "mall"), ("shop", "supermarket")),
    AttractionType.NIGHTLIFE: (("amenity", "bar"), ("amenity", "nightclub")),
    AttractionType.WELLNESS: (("leisure", "spa"),),
    AttractionType.WILDLIFE: (("tourism", "zoo"),),
    AttractionType.ADVENTURE: (("leisure", "water_park"),),
    AttractionType.FAMILY: (("leisure", "park"),),
    AttractionType.PHOTOGRAPHY: (("tourism", "viewpoint"),),
    AttractionType.FOOD: (("amenity", "restaurant"), ("amenity", "cafe")),
    AttractionType.HIKING: (("leisure", "nature_reserve"),),
    AttractionType.WATER_SPORTS: (("leisure", "water_park"), ("sport", "swimming")),
}

#: Reverse lookup built once at import time: an OSM (key, value) pair maps
#: back to whichever `AttractionType` listed it first in `_CATEGORY_TAGS`.
_TAG_TO_CATEGORY: dict[tuple[str, str], AttractionType] = {}
for _category, _pairs in _CATEGORY_TAGS.items():
    for _pair in _pairs:
        _TAG_TO_CATEGORY.setdefault(_pair, _category)


def _build_query(
    *, latitude: float, longitude: float, radius_m: int, tag_pairs: set[tuple[str, str]], limit: int
) -> str:
    """A bounded Overpass QL query — every clause is scoped by `around:`."""
    around = f"around:{radius_m},{latitude},{longitude}"
    clauses = "\n".join(f'  nwr["{key}"="{value}"]({around});' for key, value in sorted(tag_pairs))
    return (
        f"[out:json][timeout:{_QUERY_TIMEOUT_SECONDS}];\n"
        f"(\n{clauses}\n);\n"
        f"out center {limit};"
    )


def _element_category(tags: dict[str, Any]) -> AttractionType | None:
    for key, value in tags.items():
        category = _TAG_TO_CATEGORY.get((key, str(value)))
        if category is not None:
            return category
    return None


def _to_place(element: dict[str, Any]) -> RawPlace | None:
    """Map one Overpass element, or `None` if it isn't usable.

    An element with no `name` tag is dropped — recommending an unnamed place
    would be worse than recommending nothing. A `way`/`relation` carries its
    representative point in `center`, not `lat`/`lon` directly.
    """
    tags = element.get("tags")
    if not isinstance(tags, dict):
        return None
    name = tags.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    category = _element_category(tags)
    if category is None:
        return None

    if "lat" in element and "lon" in element:
        latitude, longitude = element["lat"], element["lon"]
    else:
        center = element.get("center")
        if not isinstance(center, dict):
            return None
        latitude, longitude = center.get("lat"), center.get("lon")

    if not isinstance(latitude, int | float) or not isinstance(longitude, int | float):
        return None
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        return None

    element_type = element.get("type", "node")
    element_id = element.get("id")
    if element_id is None:
        return None

    address = ", ".join(
        part
        for part in (
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:city"),
        )
        if isinstance(part, str) and part
    ) or None

    return RawPlace(
        source_id=f"{element_type}/{element_id}",
        name=name.strip(),
        category=category,
        latitude=float(latitude),
        longitude=float(longitude),
        address=address,
        tags=tuple(sorted(f"{k}={v}" for k, v in tags.items() if isinstance(v, str)))[:20],
    )


class OverpassPlacesProvider(PlacesPort):
    """`PlacesPort` backed by the public Overpass API."""

    name = "overpass"

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
        self,
        *,
        latitude: float,
        longitude: float,
        categories: tuple[AttractionType, ...],
        radius_m: int = DEFAULT_SEARCH_RADIUS_M,
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> list[RawPlace]:
        if not categories:
            return []

        tag_pairs: set[tuple[str, str]] = set()
        for category in categories:
            tag_pairs.update(_CATEGORY_TAGS.get(category, ()))
        if not tag_pairs:
            return []

        query = _build_query(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            tag_pairs=tag_pairs,
            limit=limit,
        )

        response: httpx.Response | None = None
        last_error: ProviderError | None = None

        for url in _INTERPRETER_URLS:

            async def _request(url: str = url) -> httpx.Response:
                result = await self._client.post(url, data={"data": query})
                result.raise_for_status()
                return result

            try:
                response = await call_with_retry(
                    _request,
                    provider=self.name,
                    attempts=self._retry_attempts,
                    backoff_seconds=self._retry_backoff_seconds,
                )
                break
            except ProviderError as exc:
                # Try the next mirror rather than giving up: one overloaded
                # host must not cost the trip its places.
                logger.warning("overpass_host_failed", extra={"host": url, "error": str(exc)})
                last_error = exc

        if response is None:
            raise PlacesUnavailableError(str(last_error))

        try:
            payload = response.json()
        except ValueError as exc:
            raise PlacesUnavailableError(f"[{self.name}] malformed JSON response") from exc

        if not isinstance(payload, dict):
            raise PlacesUnavailableError(f"[{self.name}] unexpected response shape")

        elements = payload.get("elements")
        if not isinstance(elements, list):
            raise PlacesUnavailableError(f"[{self.name}] unexpected 'elements' shape")

        seen: set[str] = set()
        places: list[RawPlace] = []
        for raw in elements:
            if not isinstance(raw, dict):
                continue
            place = _to_place(raw)
            if place is None or place.source_id in seen:
                continue
            seen.add(place.source_id)
            places.append(place)

        return places

    async def aclose(self) -> None:
        """Close the HTTP client this adapter was constructed with."""
        await self._client.aclose()


def build_places_service(settings: Settings, client: httpx.AsyncClient) -> OverpassPlacesProvider:
    """Wire the adapter from Phase 2 settings, sharing the provider retry policy."""
    return OverpassPlacesProvider(
        client,
        retry_attempts=settings.provider_retry_attempts,
        retry_backoff_seconds=settings.provider_retry_backoff_seconds,
    )


#: Overpass is materially slower than the weather and geocoding providers —
#: it runs a spatial query over live OSM data rather than serving a cached
#: forecast, and a multi-tag search for a trip with several interests takes
#: well over `PROVIDER_TIMEOUT_SECONDS` (5s). At that timeout every such
#: search failed, which the chat turn degrades into "no places for this
#: trip" — silently, and for exactly the interest-rich trips the product is
#: for. This is the one provider that needs its own patience; raising the
#: shared setting would slow every weather failure down with it.
_CLIENT_TIMEOUT_SECONDS = 20.0


@lru_cache
def get_places_service() -> OverpassPlacesProvider:
    """Return the process-wide Overpass adapter, constructed on first call."""
    settings = get_settings()
    client = build_http_client(_CLIENT_TIMEOUT_SECONDS)
    return build_places_service(settings, client)
