import { useQuery } from '@tanstack/react-query'

import { QUERY_CACHE, QUERY_KEYS } from '@/constants/api'
import { getIntelligence } from '@/services/api'
import type { ApiResult, IsoDate, LocationId, WeatherIntelligence } from '@/types'
import { toQueryResult } from './to-query-result'
import type { QueryResult } from './types'

export interface IntelligenceParams {
  locationId: LocationId | null
  startDate: IsoDate | null
  endDate: IsoDate | null
}

/**
 * `GET /locations/{id}/intelligence` — the dashboard's primary query.
 *
 * Disabled until the URL carries all three parameters, so an incomplete link
 * shows the "no trip to show" state instead of firing a request that would
 * `400`.
 *
 * `metadata` travels with the payload because the metadata strip, the stale
 * badge and the footer's rule-config version all read from it.
 */
export function useIntelligence({
  locationId,
  startDate,
  endDate,
}: IntelligenceParams): QueryResult<ApiResult<WeatherIntelligence>> {
  const enabled = Boolean(locationId && startDate && endDate)

  const query = useQuery({
    queryKey: QUERY_KEYS.intelligence(locationId ?? '', startDate ?? '', endDate ?? ''),
    queryFn: ({ signal }) =>
      getIntelligence(
        locationId ?? '',
        { startDate: startDate ?? '', endDate: endDate ?? '' },
        signal,
      ),
    enabled,
    ...QUERY_CACHE.intelligence,
  })

  return toQueryResult(query, enabled)
}
