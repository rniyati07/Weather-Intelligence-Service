/**
 * The shape every data hook returns.
 *
 * Deliberately identical to the subset of TanStack Query's `UseQueryResult`
 * that this app uses — `data` / `isPending` / `isError` / `error` / `refetch`.
 *
 * That is the whole point of this layer: every hook is a thin `useQuery`/
 * `useMutation` wrapper over the real backend, so a component only ever
 * consumes this shape — never an API client or an envelope — and swapping
 * what's behind a hook is never a component change.
 */

import type { ApiError } from '@/services/api'

export interface QueryResult<TData> {
  data: TData | undefined
  /** No data yet and a request is in flight. */
  isPending: boolean
  isError: boolean
  error: ApiError | null
  refetch: () => void
}

/** A query that only runs once something enables it — see `useRawWeather`. */
export interface LazyQueryOptions {
  enabled: boolean
}
