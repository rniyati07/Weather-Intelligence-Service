/**
 * API-layer constants — retry policy, cache policy, endpoint paths.
 *
 * Nothing here issues a request; these are the rules the client and the query
 * layer are configured with.
 */

import type { AnyErrorCode, IsoDate, LocationId } from '@/types'

/**
 * Endpoint paths, relative to the configured base URL.
 *
 * The published OpenAPI emits `{location_id}` where the spec prose says
 * `{locationId}` — cosmetic only, since path params are positional
 * (FDS Appendix B). `locationId` is `"{lat},{lon}"` and is encoded here.
 */
export const ENDPOINTS = {
  intelligence: (id: LocationId) => `/locations/${encodeURIComponent(id)}/intelligence`,
  bestDays: (id: LocationId) => `/locations/${encodeURIComponent(id)}/intelligence/best-days`,
  packing: (id: LocationId) => `/locations/${encodeURIComponent(id)}/intelligence/packing`,
  narrative: (id: LocationId) => `/locations/${encodeURIComponent(id)}/intelligence/narrative`,
  rawWeather: (id: LocationId) => `/locations/${encodeURIComponent(id)}/weather/raw`,
  providerHealth: () => '/providers/health',
  conversations: () => '/conversations',
  conversation: (id: string) => `/conversations/${encodeURIComponent(id)}`,
  chat: () => '/conversations/chat',
} as const

/**
 * Retry policy — FDS §7.7 / §15.5.
 *
 * `429`, `503` and network failures are worth retrying. A `4xx` client error
 * never is: the request is wrong, and repeating it repeats the mistake.
 */
export const RETRYABLE_ERROR_CODES: readonly AnyErrorCode[] = [
  'RATE_LIMITED',
  'PROVIDER_UNAVAILABLE',
  'SERVICE_DEGRADED',
  'UPSTREAM_TIMEOUT',
  'INTERNAL_ERROR',
  'NETWORK_ERROR',
  'TIMEOUT',
]

/** Cap on automatic attempts; after this the user gets an explicit retry control. */
export const MAX_AUTO_RETRIES = 2

/** Exponential backoff with jitter: 1s, 2s. `Retry-After` on a 429 wins over this. */
export const RETRY_BACKOFF_MS = [1000, 2000] as const
export const RETRY_JITTER_MS = 250

/**
 * TanStack Query cache policy — FDS §15.3.
 *
 * Narrative is cached longer than intelligence because the backend caches it on
 * the same key (location, period, ruleConfigVersion, language): refetching
 * burns an LLM call for byte-identical output.
 */
export const QUERY_CACHE = {
  intelligence: { staleTime: 5 * 60_000, gcTime: 30 * 60_000, retry: MAX_AUTO_RETRIES },
  narrative: { staleTime: 30 * 60_000, gcTime: 60 * 60_000, retry: 1 },
  rawWeather: { staleTime: 5 * 60_000, gcTime: 30 * 60_000, retry: MAX_AUTO_RETRIES },
  providerHealth: { staleTime: 30_000, gcTime: 5 * 60_000, retry: 1 },
  geocoding: { staleTime: 24 * 60 * 60_000, gcTime: 7 * 24 * 60 * 60_000, retry: 1 },
  /** Always refetched on navigation (`staleTime: 0`) — a conversation is
   * mutated by the chat endpoint, not by this query, so a cached copy can
   * never be trusted to still match server state. */
  conversation: { staleTime: 0, gcTime: 10 * 60_000, retry: MAX_AUTO_RETRIES },
  conversationList: { staleTime: 15_000, gcTime: 10 * 60_000, retry: MAX_AUTO_RETRIES },
} as const

/**
 * Query-key roots. Keys are built from these plus the URL parameters, so a
 * change of destination or dates is a different key and TanStack Query
 * deduplicates identical in-flight requests for free — which matters against a
 * 60/min rate limit when a user drags a date range (FDS §15.4).
 */
export const QUERY_KEYS = {
  intelligence: (locationId: LocationId, start: IsoDate, end: IsoDate) =>
    ['intelligence', locationId, start, end] as const,
  narrative: (locationId: LocationId, start: IsoDate, end: IsoDate, language: string) =>
    ['narrative', locationId, start, end, language] as const,
  rawWeather: (locationId: LocationId, start: IsoDate, end: IsoDate) =>
    ['raw-weather', locationId, start, end] as const,
  providerHealth: () => ['provider-health'] as const,
  geocoding: (query: string) => ['geocoding', query] as const,
  conversationList: () => ['conversations'] as const,
  conversation: (id: string) => ['conversation', id] as const,
} as const

/** Debounce before a typed query is issued (FDS §6.2). */
export const SEARCH_DEBOUNCE_MS = 300

/** Minimum characters before the geocoder is queried at all. */
export const SEARCH_MIN_CHARS = 2

/** Debounce on date-range changes, so dragging a range does not stack requests. */
export const DATE_CHANGE_DEBOUNCE_MS = 400
