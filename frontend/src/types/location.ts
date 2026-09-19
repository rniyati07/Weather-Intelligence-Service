/** Location and period — API Spec §9.2, §9.3. */

import type { IsoDate, LocationId } from './common'

/** API Spec §9.2. */
export interface Location {
  /** `"lat,lon"` in v1. Routing key; never displayed. */
  id: LocationId
  /** Human-readable name if known. Falls back to formatted coordinates when null. */
  name?: string | null
  latitude: number
  longitude: number
}

/** API Spec §9.3. Both bounds inclusive. */
export interface Period {
  startDate: IsoDate
  endDate: IsoDate
}

/**
 * A geocoding result. Not part of the backend contract — place-name resolution
 * is a client responsibility (API Spec §5), so this models the shape the
 * frontend's own geocoding provider returns.
 *
 * `admin1` and `country` are what let the UI distinguish same-named places
 * ("Goa, India" vs "Goa, Camarines Sur, Philippines"); name alone is
 * insufficient (FDS §6.2 LocationSelector).
 */
export interface GeocodedPlace {
  id: LocationId
  name: string
  /** First-level administrative region, e.g. a state or province. */
  admin1?: string | null
  country?: string | null
  countryCode?: string | null
  latitude: number
  longitude: number
  timezone?: string | null
}
