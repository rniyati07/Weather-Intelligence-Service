/**
 * Enumerations — API Spec §10.
 *
 * Every enum here is modelled as `Known | (string & {})` rather than a closed
 * union. That is deliberate: API Spec §10/§12/§15 require consumers to treat
 * enums as **open** and tolerate an unrecognised value without failing. The
 * `(string & {})` arm keeps editor autocomplete for the known members while
 * making an unknown value type-legal, so the compiler pushes callers toward an
 * exhaustive-with-fallback `switch` instead of a crash at runtime.
 */

type Open<T extends string> = T | (string & {})

/** Severity of travel disruption or hazard. */
export const RISK_LEVELS = ['low', 'moderate', 'high'] as const
export type KnownRiskLevel = (typeof RISK_LEVELS)[number]
export type RiskLevel = Open<KnownRiskLevel>

/** Severity of an individual risk factor. Same vocabulary as RiskLevel. */
export const SEVERITIES = ['low', 'moderate', 'high'] as const
export type KnownSeverity = (typeof SEVERITIES)[number]
export type Severity = Open<KnownSeverity>

/** Day-level guidance. Derived from day risk: low→proceed, moderate→caution, high→avoid. */
export const TRAVEL_ADVISORIES = ['proceed', 'caution', 'avoid'] as const
export type KnownTravelAdvisory = (typeof TRAVEL_ADVISORIES)[number]
export type TravelAdvisory = Open<KnownTravelAdvisory>

/** Fixed v1 set for suitability scoring. New categories are additive (§12). */
export const ACTIVITY_CATEGORIES = ['outdoor_sightseeing', 'beach', 'indoor_museum'] as const
export type KnownActivityCategory = (typeof ACTIVITY_CATEGORIES)[number]
export type ActivityCategory = Open<KnownActivityCategory>

/** Category of a contributing risk factor. v1 taxonomy; extensible additively. */
export const RISK_FACTOR_TYPES = ['heat', 'cold', 'rain', 'storm', 'wind'] as const
export type KnownRiskFactorType = (typeof RISK_FACTOR_TYPES)[number]
export type RiskFactorType = Open<KnownRiskFactorType>

/** Normalized internal condition vocabulary; provider codes map into this set. */
export const WEATHER_CONDITIONS = [
  'clear',
  'partly_cloudy',
  'cloudy',
  'rain',
  'heavy_rain',
  'thunderstorm',
  'snow',
  'fog',
] as const
export type KnownWeatherCondition = (typeof WEATHER_CONDITIONS)[number]
export type WeatherCondition = Open<KnownWeatherCondition>

/** Freshness of the served data. `stale` is surfaced to the user; hit/miss are silent. */
export const CACHE_STATUSES = ['hit', 'miss', 'stale'] as const
export type KnownCacheStatus = (typeof CACHE_STATUSES)[number]
export type CacheStatus = Open<KnownCacheStatus>

/** Operational provider state. Appears on `/providers/health` only. */
export const PROVIDER_STATUSES = ['available', 'degraded', 'unavailable'] as const
export type KnownProviderStatus = (typeof PROVIDER_STATUSES)[number]
export type ProviderStatus = Open<KnownProviderStatus>

/**
 * Machine-readable error codes — API Spec §7.
 *
 * Branch on these, never on the HTTP status alone: `PROVIDER_UNAVAILABLE` and
 * `SERVICE_DEGRADED` are both `503` but demand opposite UI responses — a
 * full-page error vs. an error confined to the AI Explanation card (FDS §13.3).
 */
export const ERROR_CODES = [
  'VALIDATION_ERROR',
  'AUTHENTICATION_ERROR',
  'AUTHORIZATION_ERROR',
  'NOT_FOUND',
  'RATE_LIMITED',
  'PROVIDER_UNAVAILABLE',
  'UPSTREAM_TIMEOUT',
  'SERVICE_DEGRADED',
  'INTERNAL_ERROR',
] as const
export type KnownErrorCode = (typeof ERROR_CODES)[number]
export type ErrorCode = Open<KnownErrorCode>

/**
 * Client-only error codes. The transport layer needs to describe failures the
 * backend never gets to report on — a dropped connection, a timeout on our
 * side, a response that did not match the envelope contract.
 */
export const CLIENT_ERROR_CODES = ['NETWORK_ERROR', 'TIMEOUT', 'CLIENT_ERROR', 'CANCELLED'] as const
export type ClientErrorCode = (typeof CLIENT_ERROR_CODES)[number]

/** Any code an `ApiError` can carry. */
export type AnyErrorCode = ErrorCode | ClientErrorCode
