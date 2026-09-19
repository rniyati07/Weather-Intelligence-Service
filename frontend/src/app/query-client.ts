import { QueryClient } from '@tanstack/react-query'

import { QUERY_CACHE } from '@/constants/api'
import { retryDelay, shouldRetry } from '@/services/api'

/**
 * TanStack Query configuration — FDS §15.3, §15.5.
 *
 * The defaults here are the conservative ones; per-query overrides live with
 * each hook (`QUERY_CACHE` in `constants/api` holds them).
 *
 * `refetchOnWindowFocus` is off. It is a sensible default for a dashboard of
 * live metrics and a poor one here: a user tabs away to check a flight, comes
 * back, and a refetch fires against a 60/min limit to redeliver a forecast that
 * has not changed. Freshness is handled by `staleTime` instead.
 *
 * Retries go through `shouldRetry`, which never retries a 4xx — a client error
 * means the request is wrong, and repeating it repeats the mistake.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: QUERY_CACHE.intelligence.staleTime,
        gcTime: QUERY_CACHE.intelligence.gcTime,
        retry: shouldRetry,
        retryDelay,
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
        // Every response is read-only server state; a stale render while
        // revalidating is preferable to a skeleton the user has already seen.
        placeholderData: undefined,
      },
      mutations: {
        // The only "mutation" in this product is the narrative request, which
        // is a POST that computes rather than writes. Retrying it costs an LLM
        // call, so it is opt-in per call site.
        retry: false,
      },
    },
  })
}

/** The app-wide client. Tests and stories create their own via `createQueryClient()`. */
export const queryClient = createQueryClient()
