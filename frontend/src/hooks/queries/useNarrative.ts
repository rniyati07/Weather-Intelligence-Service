import { useQuery } from '@tanstack/react-query'

import { QUERY_CACHE, QUERY_KEYS } from '@/constants/api'
import { generateNarrative } from '@/services/api'
import type { IsoDate, LanguageCode, LocationId, Narrative } from '@/types'
import { toQueryResult } from './to-query-result'
import type { QueryResult } from './types'

export interface NarrativeParams {
  locationId: LocationId | null
  startDate: IsoDate | null
  endDate: IsoDate | null
  language?: LanguageCode
}

/**
 * `POST /locations/{id}/intelligence/narrative`.
 *
 * Runs **in parallel** with the intelligence query and is never awaited before
 * the deterministic regions paint. Narration is mandatory server-side but
 * optional to the user experience: on LLM failure this rejects with
 * `503 SERVICE_DEGRADED`, and the caller confines that error to the AI
 * Explanation card while everything else stays interactive (FDS §7.2).
 *
 * A longer `staleTime` than the other queries on purpose — the backend caches
 * narration on the same key `(location, period, ruleConfigVersion, language)`,
 * so refetching burns an LLM call for byte-identical output (FDS §15.3).
 *
 * A POST, but modelled as a query rather than a mutation: it computes, it does
 * not write, and it must participate in caching and dedup like any read.
 */
export function useNarrative({
  locationId,
  startDate,
  endDate,
  language = 'en',
}: NarrativeParams): QueryResult<Narrative> {
  const enabled = Boolean(locationId && startDate && endDate)

  const query = useQuery({
    queryKey: QUERY_KEYS.narrative(locationId ?? '', startDate ?? '', endDate ?? '', language),
    queryFn: async ({ signal }) => {
      const result = await generateNarrative(
        locationId ?? '',
        { startDate: startDate ?? '', endDate: endDate ?? '', language },
        signal,
      )
      return result.data.narrative
    },
    enabled,
    ...QUERY_CACHE.narrative,
  })

  return toQueryResult(query, enabled)
}
