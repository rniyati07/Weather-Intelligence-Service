/**
 * Retry policy — FDS §7.7, §15.5.
 *
 * Wired into TanStack Query's `retry` / `retryDelay`, so every query inherits
 * it rather than each hook re-deciding.
 *
 * The rule that matters: `429`, `503` and network failures are worth retrying;
 * `400`, `401`, `403` and `404` never are. A client error means the request is
 * wrong, and repeating it just repeats the mistake — while burning budget
 * against a 60/min limit.
 */

import { MAX_AUTO_RETRIES, RETRY_BACKOFF_MS, RETRY_JITTER_MS } from '@/constants/api'
import { ApiError } from './errors'

/** `retry` predicate. Caps automatic attempts; beyond that the user retries explicitly. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_AUTO_RETRIES) return false
  if (!ApiError.is(error)) return false
  if (error.code === 'CANCELLED') return false
  return error.isRetryable
}

/**
 * `retryDelay`. Exponential backoff with jitter — except on a `429`, where the
 * server told us exactly how long to wait and guessing is worse than obeying.
 */
export function retryDelay(attemptIndex: number, error: unknown): number {
  if (ApiError.is(error) && error.retryAfterSeconds !== undefined) {
    return error.retryAfterSeconds * 1000
  }

  const base =
    RETRY_BACKOFF_MS[attemptIndex] ?? RETRY_BACKOFF_MS[RETRY_BACKOFF_MS.length - 1] ?? 2000

  // Jitter keeps a wave of clients from retrying in lockstep after an outage.
  return base + Math.random() * RETRY_JITTER_MS
}
