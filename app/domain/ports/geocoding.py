"""`GeocodingPort`: free-text place name -> candidate coordinates.

Implemented by `infrastructure.geocoding.open_meteo.OpenMeteoGeocoding`.

Until now place-name resolution was a *client* responsibility (API Spec §5):
the browser geocoded, and the backend only ever saw `"{lat},{lon}"`. A chat
endpoint changes that — a user types "Goa", not a coordinate pair — so the
backend needs its own resolver. This port is that capability, kept behind an
abstraction for the same reason `WeatherProvider` is: the adapter is the only
module that knows one external dialect.

Returning no match is an *answer*, not a failure — mirroring how a weather
adapter omits a day it cannot supply rather than fabricating one. Only an
unreachable provider raises.
"""

from abc import ABC, abstractmethod

from app.domain.entities.trip import GeocodedPlace

#: Enough candidates to disambiguate ("which Goa?") without turning a
#: clarification question into a wall of options.
DEFAULT_SEARCH_LIMIT = 5


class GeocodingUnavailableError(Exception):
    """Raised when the geocoding provider could not be consulted at all.

    Transport failure, timeout, or a malformed response — never "no such
    place", which is an empty result instead.
    """


class GeocodingPort(ABC):
    """Resolves a place name to coordinates. Never computes weather."""

    @abstractmethod
    async def search(
        self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> list[GeocodedPlace]:
        """Return candidate places for `query`, best match first.

        An empty list means the provider had no match — a legitimate result
        the caller should turn into a clarification question, never into an
        invented location. Raises `GeocodingUnavailableError` only when the
        provider itself failed.
        """
