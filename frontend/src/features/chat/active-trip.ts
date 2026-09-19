/**
 * The active-trip state machine behind the workspace.
 *
 * The product has two shapes, and which one is on screen is a property of the
 * *trip*, not of the latest message:
 *
 *   NO_ACTIVE_TRIP   conversation-first entry — no outlook, no sidebar
 *   ACTIVE_TRIP      full workspace — identity, outlook, days, places, packing
 *
 * Deriving this from `tripContext` rather than from the last turn's `intent`
 * is the whole point. An intent-driven rule made the workspace flicker out
 * whenever the user asked a packing or weather question, because those turns
 * are classified differently — but the trip did not stop existing, so the
 * workspace should not stop existing either.
 */

import type { ConversationSummary, TripContextPayload } from '@/types'

/** How many conversations the history rail shows: the current trip plus the
 * two before it. A *display* window only — the backend keeps every
 * conversation and `GET /conversations` still returns them all. */
export const HISTORY_WINDOW = 3

/**
 * The rolling history window: the active conversation first, then the most
 * recently updated others, capped at {@link HISTORY_WINDOW}.
 *
 * Pinning the active one rather than plainly slicing matters when a user
 * reopens an older trip — it is the thing they are looking at, so it belongs
 * on screen even when two newer conversations would otherwise fill the
 * window.
 */
export function rollingHistoryWindow(
  conversations: ConversationSummary[],
  activeId: string | undefined,
): ConversationSummary[] {
  const active = conversations.filter((conversation) => conversation.id === activeId)
  const rest = conversations.filter((conversation) => conversation.id !== activeId)
  return [...active, ...rest].slice(0, HISTORY_WINDOW)
}

export type TripState = 'NO_ACTIVE_TRIP' | 'ACTIVE_TRIP'

/**
 * A trip is active once the backend has resolved a destination *and* both
 * dates — exactly the inputs `GET /locations/{id}/intelligence` needs. That
 * is the same condition the backend calls `contextComplete`, but read from
 * the context itself so it holds on a restored thread, where per-turn flags
 * are not available.
 *
 * `answered` is the second half of the rule and only ever gates the *first*
 * appearance: the workspace may not materialise beside a question that has
 * not been answered yet. A brand-new conversation therefore stays
 * conversation-first until the assistant's first reply lands, even though
 * the trip context itself completes mid-turn.
 */
export function tripState(trip: TripContextPayload, answered: boolean): TripState {
  const ready = Boolean(trip.destination && trip.startDate && trip.endDate)
  return ready && answered ? 'ACTIVE_TRIP' : 'NO_ACTIVE_TRIP'
}

export function isActiveTrip(trip: TripContextPayload, answered: boolean): boolean {
  return tripState(trip, answered) === 'ACTIVE_TRIP'
}

/**
 * The `{lat},{lon}` location id for an active trip, at the 4dp the backend's
 * own `GeocodedPlace.location_id` emits. Null when no destination is
 * resolved, so callers can keep a query disabled rather than guess.
 */
export function tripLocationId(trip: TripContextPayload): string | null {
  const destination = trip.destination
  if (!destination) return null
  return `${destination.latitude.toFixed(4)},${destination.longitude.toFixed(4)}`
}

/**
 * A stable identity for "which trip is this". Used to decide when the
 * workspace is looking at a *different* trip rather than an updated one — a
 * destination or date change must not leave the previous trip's places on
 * screen.
 */
export function tripIdentity(trip: TripContextPayload): string | null {
  const locationId = tripLocationId(trip)
  if (!locationId || !trip.startDate || !trip.endDate) return null
  return `${locationId}|${trip.startDate}|${trip.endDate}`
}
