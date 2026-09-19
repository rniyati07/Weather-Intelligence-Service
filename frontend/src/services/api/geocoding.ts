/**
 * Client-side geocoding — Open-Meteo.
 *
 * Deliberately **does not** go through our backend or the BFF: place-name
 * resolution is a client responsibility (API Spec §5), and Open-Meteo's
 * geocoding endpoint is keyless. That choice is the point — client-side
 * geocoding introduces no second secret to protect (FDS §17.1).
 *
 * Uses a bare `axios` call rather than `apiClient`, because `apiClient` is
 * configured for our envelope contract and our base URL; this is a foreign API
 * with its own response shape.
 */

import axios from 'axios'

import type { GeocodedPlace } from '@/types'
import { ApiError } from './errors'

const GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'

/** The subset of Open-Meteo's response the app uses. */
interface OpenMeteoPlace {
  id: number
  name: string
  latitude: number
  longitude: number
  country?: string
  country_code?: string
  admin1?: string
  admin2?: string
  timezone?: string
}

interface OpenMeteoResponse {
  results?: OpenMeteoPlace[]
}

/** Coordinates are formatted to 4dp so the id matches what the backend echoes back. */
function toLocationId(latitude: number, longitude: number): string {
  return `${latitude.toFixed(4)},${longitude.toFixed(4)}`
}

function toGeocodedPlace(place: OpenMeteoPlace): GeocodedPlace {
  return {
    id: toLocationId(place.latitude, place.longitude),
    name: place.name,
    // `admin2` adds the district that distinguishes same-named places within a
    // region — the "Goa, Camarines Sur, Bicol" case the disambiguation list exists for.
    admin1: [place.admin1, place.admin2].filter(Boolean).join(', ') || null,
    country: place.country ?? null,
    countryCode: place.country_code ?? null,
    latitude: place.latitude,
    longitude: place.longitude,
    timezone: place.timezone ?? null,
  }
}

/** Case- and diacritic-insensitive, for comparing a query against a place name. */
function fold(value: string): string {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim()
}

/**
 * Promote exact name matches above fuzzy ones.
 *
 * Open-Meteo's search is fuzzy and ranks by population, so "Goa" returns
 * *Genoa, Italy* first — a confusing top suggestion for someone who typed the
 * name of the place they want exactly. The provider's ordering is otherwise
 * sensible, so this is a stable partition rather than a re-sort: exact matches
 * keep their relative order, and so does everything else.
 */
function rankByExactness(places: GeocodedPlace[], query: string): GeocodedPlace[] {
  // The user may have typed "Goa, India"; only the first segment is a name.
  const target = fold(query.split(',')[0] ?? query)
  if (target.length === 0) return places

  const exact = places.filter((place) => fold(place.name) === target)
  const rest = places.filter((place) => fold(place.name) !== target)

  return [...exact, ...rest]
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<GeocodedPlace[]> {
  const trimmed = query.trim()
  if (trimmed.length === 0) return []

  try {
    const response = await axios.get<OpenMeteoResponse>(GEOCODING_URL, {
      params: { name: trimmed, count: 8, language: 'en', format: 'json' },
      // Omitted rather than set to `undefined` — `exactOptionalPropertyTypes`
      // treats those as different, and axios wants a real AbortSignal.
      ...(signal ? { signal } : {}),
      timeout: 8000,
    })

    return rankByExactness((response.data.results ?? []).map(toGeocodedPlace), trimmed)
  } catch (error) {
    if (axios.isCancel(error)) {
      throw new ApiError({ code: 'CANCELLED', message: 'Search cancelled.', cause: error })
    }

    // A geocoding outage must not read as a backend outage — the destination
    // field is the only thing affected.
    throw new ApiError({
      code: 'NETWORK_ERROR',
      message: 'Could not reach the place lookup service.',
      cause: error,
    })
  }
}
