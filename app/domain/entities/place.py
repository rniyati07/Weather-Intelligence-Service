"""`RawPlace`: one place as a places provider returns it — no weather awareness.

Distinct from `attractions.Attraction`, which additionally carries
`weather_suitability`/`weather_notes` — facts that only exist once a place has
been matched against a specific day's computed intelligence. A places
provider cannot know that; it only knows what and where a place is.
"""

from dataclasses import dataclass

from app.domain.entities.attractions import AttractionType


@dataclass(frozen=True, slots=True)
class RawPlace:
    """A real place returned by a `PlacesPort` implementation.

    `source_id` is the provider's own identifier (e.g. an OSM element id) —
    kept so two searches that both return the same physical place can be
    deduplicated, and never surfaced to a user as a "provider name" (guide
    §5.3's provider-agnosty rule applies here exactly as it does to weather).
    """

    source_id: str
    name: str
    category: AttractionType
    latitude: float
    longitude: float
    address: str | None = None
    tags: tuple[str, ...] = ()


__all__ = ["RawPlace"]
