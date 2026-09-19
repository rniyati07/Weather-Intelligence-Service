/**
 * Value formatting. Pure functions, no domain decisions.
 *
 * The rule these all serve: the UI displays what the deterministic engine
 * computed. Nothing here derives a verdict, ranks a day, or infers a level —
 * it only renders values the API already produced.
 */

import { EMPTY_VALUE } from '@/constants/app'
import { DATE_LOCALE } from '@/constants/dates'
import { CONFIDENCE_BANDS } from '@/constants/domain'
import type { Location, Score, TemperatureUnit, UnitInterval } from '@/types'

/* --- Temperature ------------------------------------------------------- */

export function celsiusToFahrenheit(celsius: number): number {
  return celsius * 1.8 + 32
}

/**
 * Format a temperature in the user's chosen unit.
 *
 * The API is metric and fixed in v1 (API Spec §5), so °F is a client-side
 * conversion — which is why toggling units never triggers a refetch.
 */
export function formatTemperature(
  celsius: number | null | undefined,
  unit: TemperatureUnit = 'celsius',
  options: { withUnit?: boolean } = {},
): string {
  if (celsius == null || Number.isNaN(celsius)) return EMPTY_VALUE

  const value = unit === 'fahrenheit' ? celsiusToFahrenheit(celsius) : celsius
  const symbol = unit === 'fahrenheit' ? '°F' : '°C'
  const rounded = Math.round(value)

  return options.withUnit === false ? `${rounded}°` : `${rounded}${symbol}`
}

/** "29°C / 24°C" — max first, matching the daily card. */
export function formatTemperatureRange(
  maxC: number | null | undefined,
  minC: number | null | undefined,
  unit: TemperatureUnit = 'celsius',
): string {
  return `${formatTemperature(maxC, unit)} / ${formatTemperature(minC, unit)}`
}

/* --- Percentages and scores -------------------------------------------- */

/** 0.0–1.0 → "92%". Used for precipitation probability and humidity. */
export function formatPercent(value: UnitInterval | null | undefined): string {
  if (value == null || Number.isNaN(value)) return EMPTY_VALUE
  return `${Math.round(value * 100)}%`
}

/** "37/100" — the trip suitability and activity score rendering. */
export function formatScore(score: Score | null | undefined): string {
  if (score == null || Number.isNaN(score)) return EMPTY_VALUE
  return `${Math.round(score)}/100`
}

export function formatWindSpeed(kph: number | null | undefined): string {
  if (kph == null || Number.isNaN(kph)) return EMPTY_VALUE
  return `${Math.round(kph)} km/h`
}

/** Millimetres of precipitation. Nullable: a provider may simply not report it. */
export function formatPrecipitationMm(mm: number | null | undefined): string {
  if (mm == null || Number.isNaN(mm)) return EMPTY_VALUE
  return `${mm.toFixed(1)} mm`
}

/* --- Confidence --------------------------------------------------------- */

/**
 * `0.71` → `{ label: "Moderate confidence", tone: "moderate", value: 0.71 }`.
 *
 * FDS §6.3 is explicit: confidence is displayed as plain language. The raw
 * decimal may appear as secondary text but must never be the primary reading —
 * a confident-looking UI over a low-confidence forecast is a product failure.
 */
export function formatConfidence(confidence: UnitInterval | null | undefined) {
  if (confidence == null || Number.isNaN(confidence)) {
    return { label: 'Confidence unavailable', tone: 'unknown' as const, value: null }
  }

  const clamped = clamp(confidence, 0, 1)
  const band = CONFIDENCE_BANDS.find((candidate) => clamped >= candidate.min)
  const resolved = band ?? CONFIDENCE_BANDS[CONFIDENCE_BANDS.length - 1]

  return {
    label: resolved?.label ?? 'Confidence unavailable',
    tone: resolved?.tone ?? ('unknown' as const),
    value: clamped,
  }
}

/** The secondary reading beneath the plain-language label: "0.64 of 1.00". */
export function formatConfidenceValue(confidence: UnitInterval | null | undefined): string {
  if (confidence == null || Number.isNaN(confidence)) return EMPTY_VALUE
  return `${clamp(confidence, 0, 1).toFixed(2)} of 1.00`
}

/* --- Location ----------------------------------------------------------- */

/** "15.2993, 74.1240" — 4dp, matching the header subtitle. */
export function formatCoordinates(latitude: number, longitude: number): string {
  return `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`
}

/**
 * A location's display name, falling back to formatted coordinates when the
 * geocoder returned no name (FDS §8.8).
 */
export function formatLocation(
  location: Pick<Location, 'name' | 'latitude' | 'longitude'>,
): string {
  const name = location.name?.trim()
  return name && name.length > 0 ? name : formatCoordinates(location.latitude, location.longitude)
}

/**
 * "Goa, Camarines Sur, Philippines" — enough context to tell same-named places
 * apart, which is the whole job of the disambiguation list (FDS §6.2).
 */
export function formatPlaceContext(parts: {
  admin1?: string | null
  country?: string | null
}): string {
  return [parts.admin1, parts.country].filter((part): part is string => Boolean(part)).join(', ')
}

/* --- Text --------------------------------------------------------------- */

/**
 * `indoor_museum` → "Indoor museum".
 *
 * The fallback for an unrecognised enum member. Known slugs get a curated
 * label from `constants/domain`; this keeps an unknown one readable instead of
 * leaking a raw identifier or crashing (API Spec §12).
 */
export function titleCaseSlug(slug: string): string {
  return slug
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/^\p{Ll}/u, (char) => char.toUpperCase())
}

/** Format an integer with locale grouping. */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat(DATE_LOCALE).format(value)
}

export function formatList(items: readonly string[]): string {
  return new Intl.ListFormat(DATE_LOCALE, { style: 'long', type: 'conjunction' }).format(items)
}

/** Human-readable byte size, for the settings cache readout. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/* --- Numeric helpers ---------------------------------------------------- */

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

/** Map a 0–100 score onto 0–1, for meters and gauges. */
export function scoreToFraction(score: Score): number {
  return clamp(score, 0, 100) / 100
}
