/**
 * Conversational assistant contract — `POST /conversations/chat` and the
 * conversation-management endpoints.
 *
 * Hand-written from the actual current `ChatResponse` schema, not the FDS's
 * aspirational description of it — every field here exists on the wire
 * today. Nothing is invented ahead of the backend (master prompt, "Do not
 * invent additional fields").
 */

import type { IsoDate, IsoDateTime } from './common'

/** `ChatIntent` — a closed set server-side, but treated as open here: an
 * unrecognised value must render safely, never crash (FDS §8.7 pattern
 * applied to the chat contract). */
export type ChatIntent =
  | 'trip_planning'
  | 'itinerary_request'
  | 'weather_question'
  | 'recommendation_request'
  | 'packing_request'
  | 'general_chat'
  | (string & {})

export type MissingEssential = 'destination' | 'start_date' | 'end_date' | (string & {})

/** The destination inside `tripContext`, once resolved. */
export interface TripContextDestination {
  name: string
  displayName: string
  latitude: number
  longitude: number
  country?: string | null
  countryCode?: string | null
  admin1?: string | null
  timezone?: string | null
}

/**
 * `tripContext` on the wire is an open object — the backend only includes
 * keys it actually has something to say about (API Spec: absent fields are
 * omitted, not null). Every field is therefore optional here, and reading
 * one without a presence check is a bug.
 */
export interface TripContextPayload {
  destination?: TripContextDestination
  destinationQuery?: string
  startDate?: IsoDate
  endDate?: IsoDate
  interests?: string[]
  travelStyle?: string
  /** Free-text pace preference ("relaxed", "packed"), set when the user says
   * something like "keep it relaxed". Enrichment, never an essential. */
  pace?: string
}

/** The wire shape: an open object, matching the backend's `dict[str, Any]`
 * exactly (API Spec: absent keys are omitted, not null). Narrowed to
 * {@link TripContextPayload} by `parseTripContext`, never cast directly. */
export type RawTripContext = Record<string, unknown>

/**
 * A single real place grounding a reply — sourced from the backend Places
 * provider, never from generated text. `latitude`/`longitude`/`address` are
 * nullable because the provider does not guarantee every field for every
 * place.
 */
export interface ChatPlace {
  name: string
  type: string
  latitude: number | null
  longitude: number | null
  address: string | null
  weatherSuitability: string
  reason: string
}

/** One candidate for an ambiguous destination mention. */
export interface DestinationCandidate {
  name: string
  displayName: string
  latitude: number
  longitude: number
  country?: string | null
  countryCode?: string | null
  admin1?: string | null
}

/** `POST /conversations/chat` response — the primary contract of the product. */
export interface ChatResponse {
  conversationId: string
  response: string
  contextComplete: boolean
  missingEssentials: MissingEssential[]
  tripContext: RawTripContext
  intent: ChatIntent
  llmGenerated: boolean
  places: ChatPlace[]
  destinationCandidates: DestinationCandidate[]
}

export type MessageRole = 'user' | 'assistant' | (string & {})

/** One turn, as returned by `GET /conversations/{id}`. */
export interface ChatMessage {
  id: string
  conversationId: string
  role: MessageRole
  content: string
  metadata: Record<string, unknown>
  createdAt: IsoDateTime
}

/** Full conversation — `GET /conversations/{id}` and the create response. */
export interface Conversation {
  id: string
  tripContext: RawTripContext
  messages: ChatMessage[]
  createdAt: IsoDateTime
  updatedAt: IsoDateTime
  isActive: boolean
}

/** One row of `GET /conversations` — no message bodies, just enough to list. */
export interface ConversationSummary {
  id: string
  tripContext: RawTripContext
  createdAt: IsoDateTime
  updatedAt: IsoDateTime
  isActive: boolean
  messageCount: number
  lastMessagePreview: string | null
}

/**
 * Narrow the open `tripContext` object into the shape the UI actually reads,
 * validating each field's type rather than casting. An unexpected shape for
 * a given key (a future backend change, a malformed value) drops that key
 * rather than throwing — the same "missing stays missing, never a guess"
 * rule the backend itself follows for a field it cannot supply.
 */
export function parseTripContext(raw: RawTripContext | undefined | null): TripContextPayload {
  if (!raw || typeof raw !== 'object') return {}

  const result: TripContextPayload = {}

  const destination = raw.destination
  if (destination && typeof destination === 'object') {
    const d = destination as Record<string, unknown>
    if (
      typeof d.name === 'string' &&
      typeof d.latitude === 'number' &&
      typeof d.longitude === 'number'
    ) {
      result.destination = {
        name: d.name,
        displayName: typeof d.displayName === 'string' ? d.displayName : d.name,
        latitude: d.latitude,
        longitude: d.longitude,
        country: typeof d.country === 'string' ? d.country : null,
        countryCode: typeof d.countryCode === 'string' ? d.countryCode : null,
        admin1: typeof d.admin1 === 'string' ? d.admin1 : null,
        timezone: typeof d.timezone === 'string' ? d.timezone : null,
      }
    }
  }

  if (typeof raw.destinationQuery === 'string') result.destinationQuery = raw.destinationQuery
  if (typeof raw.startDate === 'string') result.startDate = raw.startDate
  if (typeof raw.endDate === 'string') result.endDate = raw.endDate
  if (Array.isArray(raw.interests)) {
    result.interests = raw.interests.filter((item): item is string => typeof item === 'string')
  }
  if (typeof raw.travelStyle === 'string') result.travelStyle = raw.travelStyle
  if (typeof raw.pace === 'string') result.pace = raw.pace

  return result
}
