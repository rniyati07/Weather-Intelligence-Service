import { useQuery } from '@tanstack/react-query'

import { QUERY_CACHE, QUERY_KEYS } from '@/constants/api'
import { getRawWeather } from '@/services/api'
import type { IsoDate, LocationId, RawWeatherReading } from '@/types'
import { toQueryResult } from './to-query-result'
import type { LazyQueryOptions, QueryResult } from './types'

export interface RawWeatherParams {
  locationId: LocationId | null
  startDate: IsoDate | null
  endDate: IsoDate | null
}

/**
 * `GET /locations/{id}/weather/raw` — **lazy**.
 *
 * Runs only once the raw-readings disclosure is first opened (FDS §7.3). It is
 * the one region that costs an extra request and most users never open it, so
 * `enabled` is driven by the disclosure rather than by mount. Once fetched,
 * TanStack keeps it cached, so collapsing and re-expanding costs nothing.
 */
export function useRawWeather(
  { locationId, startDate, endDate }: RawWeatherParams,
  { enabled }: LazyQueryOptions,
): QueryResult<RawWeatherReading[]> {
  const isEnabled = enabled && Boolean(locationId && startDate && endDate)

  const query = useQuery({
    queryKey: QUERY_KEYS.rawWeather(locationId ?? '', startDate ?? '', endDate ?? ''),
    queryFn: async ({ signal }) => {
      const result = await getRawWeather(
        locationId ?? '',
        { startDate: startDate ?? '', endDate: endDate ?? '' },
        signal,
      )
      return result.data.readings
    },
    enabled: isEnabled,
    ...QUERY_CACHE.rawWeather,
  })

  return toQueryResult(query, isEnabled)
}
