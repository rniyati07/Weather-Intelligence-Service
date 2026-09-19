"""A tiny curated destination-alias layer in front of `GeocodingPort`.

Live audit found that Open-Meteo's geocoding gazetteer does not return
Goa, India for the query "Goa" at any practical result count — the actual
beach state never appears; obscure same-named villages worldwide (Goa,
Philippines; Goa, Rajasthan; ...) rank above it or replace it entirely. That
is a real limitation of the chosen keyless provider's data, not a bug in
this codebase, and the fix is not to pretend the provider handles it.

Two more entries were added after a live frontend-integration pass surfaced
the same class of defect from real user queries, not assumption:

- "Kerala" — the raw provider response for this query never contains an
  Indian entry at all (verified directly against the provider, 10 results).
  The top hit is "Kerälä", a Finnish village, which the exactness-ranking
  step in `open_meteo.py` then promotes to first place because it folds
  (diacritic-stripped, casefolded) to exactly "kerala" — a real match by
  that rule's own definition, just of the wrong place, because the correct
  one was never in the candidate set to begin with. Ranking logic is not at
  fault here; the underlying gazetteer simply lacks the entry.
- "Bangalore" — the same shape of gap under the city's colloquial English
  name: the provider has no Indian entry for "Bangalore" (its one hit is an
  obscure village in Pakistan), only for "Bengaluru", its official name.

This module does not touch `OpenMeteoGeocoding` or the general resolution
pipeline at all. It is a small, explicit, isolated override: a handful of
known-ambiguous names checked before delegating to the real geocoder. Every
other query — anything not in `_ALIASES` — passes through unchanged.

Trade-off, stated plainly: this does not generalize. It fixes exactly the
names listed here and nothing else; a user typing some other ambiguous
place name still gets whatever the real provider returns. Extending the
list is a one-line addition per verified destination — deliberately kept
that cheap, and deliberately not solved with a bigger system (a full
gazetteer, a second paid geocoding provider, fuzzy country-biasing) per the
"do not over-engineer" brief. Revisit if the list grows past a handful of
entries; at that size a real dataset beats a hand-maintained dict.
"""

from app.domain.entities.trip import GeocodedPlace
from app.domain.ports.geocoding import DEFAULT_SEARCH_LIMIT, GeocodingPort

#: Keyed by a normalized (casefolded, stripped) query. Each entry is the
#: *only* candidate returned for that query — deliberately not merged with
#: whatever the real provider would also return, so the override is
#: unambiguous and traceable to this file, not a ranking tweak.
_ALIASES: dict[str, GeocodedPlace] = {
    "goa": GeocodedPlace(
        name="Goa",
        latitude=15.2993,
        longitude=74.1240,
        country="India",
        country_code="IN",
        admin1="Goa",
        timezone="Asia/Kolkata",
    ),
    "kerala": GeocodedPlace(
        name="Kerala",
        latitude=10.8505,
        longitude=76.2711,
        country="India",
        country_code="IN",
        admin1="Kerala",
        timezone="Asia/Kolkata",
    ),
    "bangalore": GeocodedPlace(
        name="Bangalore",
        latitude=12.97194,
        longitude=77.59369,
        country="India",
        country_code="IN",
        admin1="Karnataka",
        timezone="Asia/Kolkata",
    ),
}


def _normalize(query: str) -> str:
    return query.strip().casefold()


class AliasedGeocoding(GeocodingPort):
    """Checks the curated alias table first; delegates everything else."""

    def __init__(self, inner: GeocodingPort) -> None:
        self._inner = inner

    async def search(
        self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> list[GeocodedPlace]:
        alias = _ALIASES.get(_normalize(query))
        if alias is not None:
            return [alias]
        return await self._inner.search(query, limit=limit)

    async def aclose(self) -> None:
        """Delegate shutdown to the wrapped adapter, if it has one."""
        aclose = getattr(self._inner, "aclose", None)
        if aclose is not None:
            await aclose()


__all__ = ["AliasedGeocoding"]
