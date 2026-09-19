/**
 * Client-side helpers for the chat transcript.
 *
 * Two concerns live here:
 *
 *   1. Building a locally-originated `ChatMessage` for optimistic rendering —
 *      the user's own message, shown before the server confirms it, and the
 *      assistant's reply, shown from the mutation's own response rather than
 *      waiting on a follow-up `GET`.
 *
 *   2. Reading the *extra* structured fields (`places`, `destinationCandidates`,
 *      `contextComplete`, `missingEssentials`, `tripContext`) a `ChatResponse`
 *      carries but a persisted `Message.metadata` does not — the backend only
 *      ever persists `intent`/`llm_generated` per turn (see
 *      `app/application/use_cases/chat_orchestrator.py`). Attaching the rest
 *      to the local message's `metadata` is a client-only augmentation: it
 *      renders correctly for a turn sent *this session* and degrades to "no
 *      extras" — never a guess — for history restored from `GET
 *      /conversations/{id}`, which the type reflects with every field optional.
 */

import type {
  ChatIntent,
  ChatMessage,
  ChatPlace,
  ChatResponse,
  DestinationCandidate,
  MissingEssential,
  RawTripContext,
  TripContextPayload,
} from '@/types'
import { parseTripContext } from '@/types'
import { tripIdentity } from '@/features/chat/active-trip'

/** Fields this client attaches to an assistant message's `metadata`, beyond
 * whatever the backend itself may have put there. Every key is optional
 * because a message restored from `GET /conversations/{id}` will have none
 * of them — only `intent` and `llmGenerated` ever come back from the server. */
export interface ChatTurnExtras {
  intent?: ChatIntent
  llmGenerated?: boolean
  places?: ChatPlace[]
  destinationCandidates?: DestinationCandidate[]
  contextComplete?: boolean
  missingEssentials?: MissingEssential[]
  tripContext?: RawTripContext
}

function randomId(): string {
  return typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `local-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

/** A message that exists only on this client — not yet, or never to be,
 * confirmed by a `GET`. Used for the optimistic user bubble and for the
 * assistant reply built straight from a `ChatResponse`. */
export function createLocalMessage(
  conversationId: string,
  role: 'user' | 'assistant',
  content: string,
  metadata: Record<string, unknown> = {},
): ChatMessage {
  return {
    id: randomId(),
    conversationId,
    role,
    content,
    metadata,
    createdAt: new Date().toISOString(),
  }
}

/** Build the assistant message for a turn straight from its `ChatResponse` —
 * response text plus every structured field the reply is grounded in. */
export function assistantMessageFromResponse(response: ChatResponse): ChatMessage {
  const extras: ChatTurnExtras = {
    intent: response.intent,
    llmGenerated: response.llmGenerated,
    places: response.places,
    destinationCandidates: response.destinationCandidates,
    contextComplete: response.contextComplete,
    missingEssentials: response.missingEssentials,
    tripContext: response.tripContext,
  }
  return createLocalMessage(
    response.conversationId,
    'assistant',
    response.response,
    extras as Record<string, unknown>,
  )
}

function readExtras(message: ChatMessage): ChatTurnExtras {
  return message.metadata
}

export function getMessageIntent(message: ChatMessage): ChatIntent | undefined {
  const value = readExtras(message).intent
  return typeof value === 'string' ? value : undefined
}

export function getMessageLlmGenerated(message: ChatMessage): boolean | undefined {
  const value = readExtras(message).llmGenerated
  return typeof value === 'boolean' ? value : undefined
}

export function getMessagePlaces(message: ChatMessage): ChatPlace[] {
  const value = readExtras(message).places
  return Array.isArray(value) ? value : []
}

export function getMessageDestinationCandidates(message: ChatMessage): DestinationCandidate[] {
  const value = readExtras(message).destinationCandidates
  return Array.isArray(value) ? value : []
}

export function getMessageContextComplete(message: ChatMessage): boolean | undefined {
  const value = readExtras(message).contextComplete
  return typeof value === 'boolean' ? value : undefined
}

export function getMessageMissingEssentials(message: ChatMessage): MissingEssential[] {
  const value = readExtras(message).missingEssentials
  return Array.isArray(value) ? value : []
}

export function getMessageTripContext(message: ChatMessage): RawTripContext | undefined {
  const value = readExtras(message).tripContext
  return value && typeof value === 'object' ? value : undefined
}

/**
 * Suggested next questions for the turn that just landed — derived from its
 * own structured state, never a fixed set repeated on every message (master
 * prompt, "Follow-Up Suggestions": "Do NOT hardcode the same four buttons for
 * every conversation").
 *
 * Driven by the server's own `intent` classification plus what that turn
 * actually returned, so the offered questions move the conversation forward
 * rather than repeating what was just answered. No suggestions while the trip
 * is still being established or a destination is ambiguous — there is nothing
 * useful to follow up on yet.
 */
export function deriveFollowUpSuggestions(message: ChatMessage): string[] {
  if (message.role !== 'assistant') return []

  const contextComplete = getMessageContextComplete(message)
  const destinationCandidates = getMessageDestinationCandidates(message)
  if (contextComplete !== true || destinationCandidates.length > 0) return []

  const places = getMessagePlaces(message)
  const intent = getMessageIntent(message)
  const suggestions: string[] = []

  if (intent !== 'weather_question') suggestions.push('Which day is best?')
  if (intent !== 'weather_question') suggestions.push('What if it rains?')

  if (places.length > 0) {
    const nearby = places[0]?.name
    suggestions.push(nearby ? `More places near ${nearby}` : 'More places nearby')
  } else if (intent !== 'recommendation_request') {
    suggestions.push('What places can I visit?')
  }

  if (intent !== 'packing_request') suggestions.push('What should I pack?')
  if (intent === 'weather_question') suggestions.push('Tell me more about this day.')

  return suggestions.slice(0, 4)
}

/**
 * The freshest `tripContext` any turn in the transcript carried.
 *
 * Only turns sent *this session* have one: a thread restored from
 * `GET /conversations/{id}` carries no per-turn extras, which is why the
 * caller falls back to the conversation's own stored context. Returns null
 * rather than an empty object so that fallback stays distinguishable from "a
 * turn that genuinely reported an empty context".
 */
export function latestTripContext(messages: ChatMessage[]): TripContextPayload | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (!message || message.role !== 'assistant') continue
    const raw = getMessageTripContext(message)
    if (raw) return parseTripContext(raw)
  }
  return null
}

/**
 * The active trip's current place shortlist: the most recent turn that
 * returned any, searching back only as far as the trip stayed the same.
 *
 * Two rules are doing work here. Looking *back* past the last turn is what
 * keeps the panel populated when the newest turn legitimately fetched none —
 * a packing question returns no places, and that must not blank the trip's
 * places. Stopping at a turn whose `tripContext` describes a different trip
 * is what stops the *previous* destination's places surviving a "let's go to
 * Bali instead", which would be worse than showing none.
 *
 * Turns restored from `GET /conversations/{id}` carry the backend's own
 * persisted `places` metadata but no `tripContext`, so an unknown identity is
 * treated as "still this trip" — the conversation is the trip's, and the
 * caller already scopes it to the conversation being viewed.
 */
export function latestPlaces(messages: ChatMessage[], tripKey: string | null): ChatPlace[] {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (!message || message.role !== 'assistant') continue

    const raw = getMessageTripContext(message)
    if (raw && tripKey !== null) {
      const identity = tripIdentity(parseTripContext(raw))
      if (identity !== null && identity !== tripKey) return []
    }

    const places = getMessagePlaces(message)
    if (places.length > 0) return places
  }
  return []
}
