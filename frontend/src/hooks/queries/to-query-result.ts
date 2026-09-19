import type { UseQueryResult } from '@tanstack/react-query'

import { ApiError, toApiError } from '@/services/api'
import type { QueryResult } from './types'

/**
 * Narrow TanStack's result to the small contract components consume.
 *
 * Two jobs. It guarantees `error` is always an `ApiError` — TanStack types it
 * as `Error`, and every call site branches on `error.code`. And it reports a
 * *disabled* query as settled rather than pending: TanStack leaves
 * `isPending: true` forever when `enabled` is false, which would leave the
 * lazily-loaded raw-readings section stuck on a skeleton it never asked for.
 */
export function toQueryResult<TData>(
  query: UseQueryResult<TData, Error>,
  enabled = true,
): QueryResult<TData> {
  return {
    data: query.data,
    isPending: enabled && query.isPending,
    isError: query.isError,
    error: query.error ? (ApiError.is(query.error) ? query.error : toApiError(query.error)) : null,
    refetch: () => {
      void query.refetch()
    },
  }
}
