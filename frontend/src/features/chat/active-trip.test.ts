import { describe, expect, it } from 'vitest'

import type { ChatMessage, ConversationSummary, TripContextPayload } from '@/types'
import { latestPlaces, withLastResolvedDestination } from '@/utils/chat'
import {
  isActiveTrip,
  rollingHistoryWindow,
  tripIdentity,
  tripLocationId,
  tripState,
} from './active-trip'

const GOA = {
  name: 'Goa',
  displayName: 'Goa, India',
  latitude: 15.2993,
  longitude: 74.124,
}

const BALI = {
  name: 'Bali',
  displayName: 'Bali, Indonesia',
  latitude: -8.4095,
  longitude: 115.1889,
}

function trip(overrides: Partial<TripContextPayload> = {}): TripContextPayload {
  return { destination: GOA, startDate: '2026-09-15', endDate: '2026-09-18', ...overrides }
}

function assistant(metadata: Record<string, unknown>): ChatMessage {
  return {
    id: crypto.randomUUID(),
    conversationId: 'c1',
    role: 'assistant',
    content: 'reply',
    metadata,
    createdAt: new Date().toISOString(),
  }
}

const PLACE = {
  name: 'Baga Beach',
  type: 'beach',
  latitude: null,
  longitude: null,
  address: null,
  weatherSuitability: 'ideal',
  reason: 'Clear, 24-31C.',
}

describe('trip state', () => {
  it('is NO_ACTIVE_TRIP before the backend has resolved anything', () => {
    expect(tripState({}, true)).toBe('NO_ACTIVE_TRIP')
    expect(isActiveTrip({}, true)).toBe(false)
  })

  it('stays NO_ACTIVE_TRIP while the trip is only partly established', () => {
    expect(tripState({ destination: GOA }, true)).toBe('NO_ACTIVE_TRIP')
    expect(tripState({ destination: GOA, startDate: '2026-09-15' }, true)).toBe('NO_ACTIVE_TRIP')
    expect(tripState({ startDate: '2026-09-15', endDate: '2026-09-18' }, true)).toBe(
      'NO_ACTIVE_TRIP',
    )
  })

  it('stays conversation-first until the assistant has actually replied', () => {
    // The context completes mid-turn, so without this the workspace would
    // appear beside a question that has not been answered yet.
    expect(tripState(trip(), false)).toBe('NO_ACTIVE_TRIP')
    expect(isActiveTrip(trip(), false)).toBe(false)
  })

  it('becomes ACTIVE_TRIP once the trip is complete and answered', () => {
    expect(tripState(trip(), true)).toBe('ACTIVE_TRIP')
    expect(isActiveTrip(trip(), true)).toBe(true)
  })

  it('does not depend on the latest turn, so follow-ups keep the trip active', () => {
    // The same context a packing, weather or places question would leave
    // behind — none of them change the trip, so none of them may end it.
    expect(isActiveTrip(trip(), true)).toBe(true)
    expect(isActiveTrip(trip({ interests: ['beaches'] }), true)).toBe(true)
    expect(isActiveTrip(trip({ pace: 'relaxed', travelStyle: 'family' }), true)).toBe(true)
  })

  it('builds the location id at the 4dp the backend emits', () => {
    expect(tripLocationId(trip())).toBe('15.2993,74.1240')
    expect(tripLocationId({})).toBeNull()
  })

  it('changes identity when the destination or the dates change', () => {
    const base = tripIdentity(trip())

    expect(tripIdentity(trip())).toBe(base)
    expect(tripIdentity(trip({ destination: BALI }))).not.toBe(base)
    expect(tripIdentity(trip({ startDate: '2026-10-01' }))).not.toBe(base)
    expect(tripIdentity(trip({ endDate: '2026-10-05' }))).not.toBe(base)
  })

  it('has no identity until the trip is complete', () => {
    expect(tripIdentity({ destination: GOA })).toBeNull()
  })
})

describe('places for the active trip', () => {
  const key = tripIdentity(trip())

  it('keeps the last real results when a later turn fetched none', () => {
    // A packing question returns no places; that must not blank the panel.
    const messages = [
      assistant({ places: [PLACE], tripContext: trip() }),
      assistant({ places: [], tripContext: trip() }),
    ]

    expect(latestPlaces(messages, key)).toHaveLength(1)
  })

  it('drops places belonging to a previous destination', () => {
    const messages = [
      assistant({ places: [PLACE], tripContext: trip() }),
      assistant({ tripContext: trip({ destination: BALI }) }),
    ]

    expect(latestPlaces(messages, tripIdentity(trip({ destination: BALI })))).toEqual([])
  })

  it('drops places belonging to a previous date range', () => {
    const messages = [
      assistant({ places: [PLACE], tripContext: trip() }),
      assistant({ tripContext: trip({ startDate: '2026-10-01', endDate: '2026-10-04' }) }),
    ]

    const changed = tripIdentity(trip({ startDate: '2026-10-01', endDate: '2026-10-04' }))
    expect(latestPlaces(messages, changed)).toEqual([])
  })

  it('reads places a restored thread persisted, even without a tripContext', () => {
    // `GET /conversations/{id}` replays the backend's own persisted metadata,
    // which carries places but no per-turn tripContext.
    expect(latestPlaces([assistant({ places: [PLACE] })], key)).toHaveLength(1)
  })

  it('returns nothing rather than throwing when no turn has places', () => {
    expect(latestPlaces([assistant({})], key)).toEqual([])
    expect(latestPlaces([], key)).toEqual([])
  })
})

/** A trip mid-disambiguation: the backend has cleared `destination` (never
 * sets it to `undefined` — it omits the key, exactly as the wire payload
 * would), while every other field the user had already established survives. */
function tripPendingDisambiguation(
  overrides: Partial<Omit<TripContextPayload, 'destination'>> = {},
): TripContextPayload {
  return { startDate: '2026-09-15', endDate: '2026-09-18', ...overrides }
}

describe('surviving a pending disambiguation (ISSUE-1)', () => {
  it('leaves an already-resolved trip untouched', () => {
    expect(withLastResolvedDestination(trip(), [])).toEqual(trip())
  })

  it('patches a cleared destination back in from the last turn that resolved one', () => {
    const messages = [
      assistant({ tripContext: trip() }),
      // The backend clears `destination` to force disambiguation on a new,
      // ambiguous mention — everything else about the trip survives.
      assistant({
        tripContext: tripPendingDisambiguation({ interests: ['photography'] }),
      }),
    ]

    const patched = withLastResolvedDestination(
      tripPendingDisambiguation({ interests: ['photography'] }),
      messages,
    )

    // `tripContext` round-trips through `parseTripContext`, which normalizes
    // the destination shape (adds e.g. `country: null` when absent from the
    // raw payload) — so only the identifying fields are asserted here, not a
    // byte-identical object.
    expect(patched.destination?.name).toBe(GOA.name)
    expect(patched.destination?.latitude).toBe(GOA.latitude)
    expect(patched.destination?.longitude).toBe(GOA.longitude)
    expect(patched.interests).toEqual(['photography'])
    expect(isActiveTrip(patched, true)).toBe(true)
  })

  it('leaves a conversation with no prior resolved destination as no-active-trip', () => {
    // A brand-new conversation whose very first mention is ambiguous must not
    // be treated as an established trip — there is nothing to fall back to.
    const messages = [assistant({ tripContext: tripPendingDisambiguation() })]

    const patched = withLastResolvedDestination(tripPendingDisambiguation(), messages)

    expect(patched.destination).toBeUndefined()
    expect(isActiveTrip(patched, true)).toBe(false)
  })

  it('ignores turns with no tripContext at all, as a restored thread has', () => {
    const messages = [assistant({ places: [] })]

    expect(
      withLastResolvedDestination(tripPendingDisambiguation(), messages).destination,
    ).toBeUndefined()
  })
})

describe('rolling history window', () => {
  function summary(id: string): ConversationSummary {
    return {
      id,
      tripContext: {},
      createdAt: '2026-09-15T00:00:00Z',
      updatedAt: '2026-09-15T00:00:00Z',
      isActive: true,
      messageCount: 2,
      lastMessagePreview: null,
    }
  }

  it('grows to three and then rolls the oldest off', () => {
    // The backend returns newest-first, so each new conversation lands at
    // the head: A → B,A → C,B,A → D,C,B.
    const ids = (list: ConversationSummary[]) => list.map((c) => c.id)

    expect(ids(rollingHistoryWindow([summary('A')], 'A'))).toEqual(['A'])
    expect(ids(rollingHistoryWindow([summary('B'), summary('A')], 'B'))).toEqual(['B', 'A'])
    expect(ids(rollingHistoryWindow([summary('C'), summary('B'), summary('A')], 'C'))).toEqual([
      'C',
      'B',
      'A',
    ])
    expect(
      ids(rollingHistoryWindow([summary('D'), summary('C'), summary('B'), summary('A')], 'D')),
    ).toEqual(['D', 'C', 'B'])
  })

  it('keeps the conversation being viewed even when it is not among the newest', () => {
    // Reopening an older trip must not hide the thing on screen.
    const all = [summary('D'), summary('C'), summary('B'), summary('A')]

    expect(rollingHistoryWindow(all, 'A').map((c) => c.id)).toEqual(['A', 'D', 'C'])
  })

  it('falls back to the newest three when nothing is active', () => {
    const all = [summary('D'), summary('C'), summary('B'), summary('A')]

    expect(rollingHistoryWindow(all, undefined).map((c) => c.id)).toEqual(['D', 'C', 'B'])
  })

  it('never invents entries when the backend returned fewer', () => {
    expect(rollingHistoryWindow([], undefined)).toEqual([])
  })
})
