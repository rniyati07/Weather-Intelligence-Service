"""`PlacesPort`: real-world place discovery, behind one contract.

The single fix this stabilization pass exists to make structural rather than
requested-of-a-prompt: attraction recommendations must be able to trace every
name back to a call through this port. No implementation behind it may
invent a place — an implementation that can't find one returns an empty
list, exactly like `GeocodingPort.search` returns no match rather than a
guess, and `WeatherProvider.fetch` drops a day it can't supply rather than
fabricating one.
"""

from abc import ABC, abstractmethod

from app.domain.entities.attractions import AttractionType
from app.domain.entities.place import RawPlace

#: A ~city-district radius — wide enough that a real destination has
#: multiple categories represented, narrow enough that results stay locally
#: relevant rather than pulling in an entire region.
DEFAULT_SEARCH_RADIUS_M = 15_000

#: Per-category result cap. Bounds both the provider query cost and the
#: amount of ranking work the matching engine does per category.
DEFAULT_RESULT_LIMIT = 40


class PlacesUnavailableError(Exception):
    """Raised when the places provider could not be consulted at all.

    Transport failure, timeout, or a malformed response — never "no places
    of this category near here", which is an empty list instead.
    """


class PlacesPort(ABC):
    """Finds real places near a location, filtered by category. Never invents one."""

    @abstractmethod
    async def search(
        self,
        *,
        latitude: float,
        longitude: float,
        categories: tuple[AttractionType, ...],
        radius_m: int = DEFAULT_SEARCH_RADIUS_M,
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> list[RawPlace]:
        """Return named places near `(latitude, longitude)` in any of `categories`.

        An empty list is a legitimate result — no matching places exist in
        range — and must be treated as such by every caller. Raises
        `PlacesUnavailableError` only when the provider itself failed.
        """


__all__ = [
    "DEFAULT_RESULT_LIMIT",
    "DEFAULT_SEARCH_RADIUS_M",
    "PlacesPort",
    "PlacesUnavailableError",
]
