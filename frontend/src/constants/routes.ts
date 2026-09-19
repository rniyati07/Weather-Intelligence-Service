/**
 * Route paths. The single place a URL string is written.
 *
 * The URL is the source of truth for a query (FDS §15.2): a results URL fully
 * determines what is fetched, which is what makes results shareable,
 * deep-linkable and refresh-stable. Builders are exported so no caller
 * hand-concatenates a path.
 */

import type { IsoDate, LocationId } from '@/types'

export const ROUTES = {
  /** Chat entry — the primary experience. Opens a fresh conversation. */
  home: '/',
  /** Active conversation thread, once one exists. */
  chat: '/chat/:conversationId',
  plan: '/plan',
  /** Deep-dive dashboard. `results` is kept mounted on the same page
   * component so an old `/results?location=` link never 404s. */
  trip: '/trip/:locationId',
  results: '/results',
  about: '/about',
  settings: '/settings',
  notFound: '*',
} as const

export type RouteKey = keyof typeof ROUTES
export type RoutePath = (typeof ROUTES)[RouteKey]

/** Query-parameter names carried in the URL. */
export const QUERY_PARAMS = {
  locationId: 'location',
  startDate: 'start',
  endDate: 'end',
  /** Prefills the planner's destination field when arriving from a search. */
  query: 'q',
} as const

/**
 * Build a deep-dive dashboard URL — `/trip/:locationId?start=&end=` (FDS
 * Revision 2 §4.1). `locationId` is a path segment, not a query value, so it
 * is percent-encoded the same way any other path segment would be.
 */
export function buildTripPath(params: {
  locationId: LocationId
  startDate: IsoDate
  endDate: IsoDate
}): string {
  const search = new URLSearchParams({
    [QUERY_PARAMS.startDate]: params.startDate,
    [QUERY_PARAMS.endDate]: params.endDate,
  })
  return `/trip/${encodeURIComponent(params.locationId)}?${search.toString()}`
}

/** @deprecated Superseded by {@link buildTripPath}. Kept only so an old
 * `/results?location=` bookmark still resolves via the compat route. */
export function buildResultsPath(params: {
  locationId: LocationId
  startDate: IsoDate
  endDate: IsoDate
}): string {
  const search = new URLSearchParams({
    [QUERY_PARAMS.locationId]: params.locationId,
    [QUERY_PARAMS.startDate]: params.startDate,
    [QUERY_PARAMS.endDate]: params.endDate,
  })
  return `${ROUTES.results}?${search.toString()}`
}

/** Build an active-conversation URL. */
export function buildChatPath(conversationId: string): string {
  return `/chat/${encodeURIComponent(conversationId)}`
}

/**
 * Build a planner URL, optionally prefilling the destination field.
 *
 * The landing page only collects a place *name*; resolving it to coordinates is
 * the planner's job, so the search hands over the raw text rather than
 * pretending to have geocoded it.
 */
export function buildPlanPath(query?: string): string {
  const trimmed = query?.trim()
  if (!trimmed) return ROUTES.plan

  const search = new URLSearchParams({ [QUERY_PARAMS.query]: trimmed })
  return `${ROUTES.plan}?${search.toString()}`
}

/**
 * Primary navigation, in tab order.
 *
 * Deliberately short. The header's job is to get someone into a search, so it
 * carries the one action that does that; About is reachable from the footer and
 * from the landing page's provenance line, where a sceptical reader is actually
 * looking for it.
 */
export const NAV_LINKS = [{ to: ROUTES.plan, label: 'Plan a trip' }] as const
