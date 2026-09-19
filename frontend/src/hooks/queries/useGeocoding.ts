import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'

import { QUERY_CACHE, QUERY_KEYS, SEARCH_DEBOUNCE_MS, SEARCH_MIN_CHARS } from '@/constants/api'
import { STORAGE_KEYS, STORAGE_TTL_MS } from '@/constants/storage'
import { searchPlaces } from '@/services/api'
import { readStorage, writeStorage } from '@/services/storage'
import type { GeocodedPlace, LocationId } from '@/types'
import { useDebounce } from '../useDebounce'
import { toQueryResult } from './to-query-result'
import type { QueryResult } from './types'

/**
 * Place-name → coordinates, via Open-Meteo.
 *
 * Geocoding is a client responsibility (API Spec §5) and deliberately does not
 * pass through our backend or the BFF — the provider is keyless, so this adds
 * no second secret to protect (FDS §17.1).
 *
 * Debouncing and the minimum query length live here rather than in the
 * component, so every consumer gets the same rate discipline.
 *
 * Successful lookups are written to a `localStorage` cache keyed by
 * `locationId`. That cache is what lets `useResolvedPlace` name a destination
 * on the dashboard, where the URL carries only coordinates.
 */
export function useGeocoding(query: string): QueryResult<GeocodedPlace[]> & { isTyping: boolean } {
  const debounced = useDebounce(query, SEARCH_DEBOUNCE_MS)
  const trimmed = debounced.trim()
  const enabled = trimmed.length >= SEARCH_MIN_CHARS

  const result = useQuery({
    queryKey: QUERY_KEYS.geocoding(trimmed),
    queryFn: async ({ signal }) => {
      const places = await searchPlaces(trimmed, signal)
      cachePlaces(places)
      return places
    },
    enabled,
    ...QUERY_CACHE.geocoding,
  })

  const normalized = toQueryResult(result, enabled)

  return {
    ...normalized,
    data: enabled ? normalized.data : [],
    // A query still settling is not a query that found nothing — without this
    // the "no results" state flashes on every keystroke.
    isTyping: query !== debounced,
  }
}

/**
 * Reverse lookup: `"{lat},{lon}"` → a named place.
 *
 * Used by the header chip, which has only the coordinate pair from the URL.
 * Reads the geocoding cache rather than issuing a request: the place was
 * resolved on the planner screen moments earlier, and the URL is the only thing
 * that survived the navigation. Returns null for a coordinate the user never
 * searched — a shared link opened on another device — and the caller falls back
 * to formatted coordinates, exactly as it does when the API returns a null name
 * (FDS §8.8).
 */
export function useResolvedPlace(locationId: LocationId | null): GeocodedPlace | null {
  const queryClient = useQueryClient()

  return useMemo(() => {
    if (!locationId) return null

    // Prefer an in-memory hit from this session before touching storage.
    const cached = queryClient
      .getQueriesData<GeocodedPlace[]>({ queryKey: ['geocoding'] })
      .flatMap(([, places]) => places ?? [])
      .find((place) => place.id === locationId)

    return cached ?? readPlaceCache()[locationId] ?? null
  }, [locationId, queryClient])
}

/* --- localStorage place cache ------------------------------------------- */

type PlaceCache = Record<string, GeocodedPlace>

function readPlaceCache(): PlaceCache {
  return readStorage<PlaceCache>(STORAGE_KEYS.geocodeCache, {})
}

function cachePlaces(places: GeocodedPlace[]): void {
  if (places.length === 0) return

  const cache = readPlaceCache()
  for (const place of places) cache[place.id] = place
  writeStorage(STORAGE_KEYS.geocodeCache, cache, STORAGE_TTL_MS.geocodeCache)
}
