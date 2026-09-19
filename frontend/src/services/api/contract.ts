/**
 * Compile-time binding between the hand-written domain types and the schema
 * generated from `/openapi.json`.
 *
 * Nothing here runs. Its whole job is to make **backend contract drift a build
 * failure instead of a runtime surprise**: if a field is renamed, made
 * nullable, or dropped upstream, regenerating `schema.d.ts` breaks compilation
 * here rather than producing `undefined` somewhere inside a card.
 *
 * The domain types stay hand-written because they carry the reasoning the
 * generated file cannot (why `narrative` is always null on `GET /intelligence`,
 * why enums are open, why `precipitationMm` renders as "—"). This module is
 * what keeps them honest.
 *
 * Regenerate with:
 *   npm run generate:api
 */

import type { components } from './schema'
import type {
  ApiEnvelope,
  ChatMessage,
  ChatPlace,
  ChatResponse,
  Conversation,
  ConversationSummary,
  DailyIntelligence,
  DestinationCandidate,
  Location,
  Narrative,
  NarrativeRequest,
  Period,
  ProviderHealth,
  RawWeatherReading,
  ResponseMetadata,
  TripSummary,
  WeatherIntelligence,
} from '@/types'

type Schemas = components['schemas']

/**
 * Asserts that `Actual` is assignable to `Expected` — i.e. every field the app
 * reads really is provided by the backend, with a compatible type.
 *
 * The check is deliberately one-directional. The generated types model enums as
 * bare `string`; ours narrow them to known members plus an open arm. Requiring
 * mutual assignability would reject that intentional narrowing, so the
 * assertion is "the wire shape satisfies what the UI consumes".
 */
type Satisfies<Expected, Actual extends Expected> = Actual

export type _Location = Satisfies<
  Omit<Location, 'name'> & { name?: string | null },
  Schemas['LocationSchema']
>
export type _Period = Satisfies<Period, Schemas['PeriodSchema']>
export type _TripSummary = Satisfies<
  Omit<TripSummary, 'overallRiskLevel'> & { overallRiskLevel: string },
  Schemas['TripSummarySchema']
>
export type _DailyIntelligence = Satisfies<
  Omit<DailyIntelligence, 'summary' | 'riskAssessment' | 'travelAdvisory'> & {
    summary: Schemas['DailySummarySchema']
    riskAssessment: Schemas['RiskAssessmentSchema']
    travelAdvisory: string
  },
  Schemas['DailyIntelligenceSchema']
>
export type _RawWeatherReading = Satisfies<
  Omit<RawWeatherReading, 'condition' | 'precipitationMm' | 'humidity'> & {
    condition: string
    precipitationMm?: number | null
    humidity?: number | null
  },
  Schemas['RawWeatherReadingSchema']
>
export type _Narrative = Satisfies<
  Omit<Narrative, 'modelUsed'> & { modelUsed?: string | null },
  Schemas['NarrativeSchema']
>
export type _NarrativeRequest = Satisfies<
  Omit<NarrativeRequest, 'language'> & { language?: string | null },
  Schemas['NarrativeRequestSchema']
>
export type _Metadata = Satisfies<
  Omit<ResponseMetadata, 'apiVersion' | 'cacheStatus'> & {
    apiVersion?: string
    cacheStatus?: string | null
  },
  Schemas['MetadataSchema']
>
export type _ProviderHealth = Satisfies<
  Omit<ProviderHealth, 'status'> & { status: string },
  Schemas['ProviderHealthSchema']
>

/** The envelope itself — `data` and `error` nullable, `metadata` always present. */
export type _Envelope = Satisfies<
  Omit<ApiEnvelope<unknown>, 'data' | 'metadata' | 'error'> & {
    data: Schemas['WeatherIntelligenceSchema'] | null
    metadata: Schemas['MetadataSchema']
    error?: Schemas['ErrorSchema'] | null
  },
  Schemas['ResponseEnvelope_WeatherIntelligenceSchema_']
>

/**
 * `narrative` is optional on the wire and **always null** on `GET /intelligence`
 * — it is populated only by the separate narrative endpoint (API Spec §9.1).
 */
export type _Intelligence = Satisfies<
  Omit<WeatherIntelligence, 'dailyIntelligence' | 'tripSummary' | 'narrative'> & {
    dailyIntelligence: Schemas['DailyIntelligenceSchema'][]
    tripSummary: Schemas['TripSummarySchema']
    narrative?: Schemas['NarrativeSchema'] | null
  },
  Schemas['WeatherIntelligenceSchema']
>

/* ---------------------------------------------------------------------------
 * Chat contract — `POST /conversations/chat` and conversation management.
 * ------------------------------------------------------------------------ */

export type _ChatPlace = Satisfies<
  Omit<ChatPlace, 'latitude' | 'longitude' | 'address'> & {
    latitude?: number | null
    longitude?: number | null
    address?: string | null
  },
  Schemas['PlaceSchema']
>

export type _DestinationCandidate = Satisfies<
  Omit<DestinationCandidate, 'country' | 'countryCode' | 'admin1'> & {
    country?: string | null
    countryCode?: string | null
    admin1?: string | null
  },
  Schemas['DestinationCandidateSchema']
>

/**
 * `places` / `destinationCandidates` are optional on the wire (a Pydantic
 * default, not a required field) but always present at runtime — the
 * backend's own test suite asserts this. The hand-written `ChatResponse`
 * keeps them required for callers; this assertion is the one place that
 * optionality is reconciled with the generated schema.
 */
export type _ChatResponse = Satisfies<
  Omit<ChatResponse, 'places' | 'destinationCandidates' | 'tripContext'> & {
    places?: Schemas['PlaceSchema'][]
    destinationCandidates?: Schemas['DestinationCandidateSchema'][]
    tripContext: Record<string, unknown>
  },
  Schemas['ChatResponse']
>

export type _ChatMessage = Satisfies<
  Omit<ChatMessage, 'metadata'> & { metadata: Record<string, unknown> },
  Schemas['MessageSchema']
>

export type _Conversation = Satisfies<
  Omit<Conversation, 'messages' | 'tripContext'> & {
    messages: Schemas['MessageSchema'][]
    tripContext: Record<string, unknown>
  },
  Schemas['ConversationSchema']
>

export type _ConversationSummary = Satisfies<
  Omit<ConversationSummary, 'tripContext' | 'lastMessagePreview'> & {
    tripContext: Record<string, unknown>
    lastMessagePreview?: string | null
  },
  Schemas['ConversationListItem']
>
