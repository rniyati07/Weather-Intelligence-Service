/**
 * Domain vocabulary → presentation.
 *
 * Enum-to-label and enum-to-tone maps live here rather than inside components,
 * so a new backend enum value is a one-line change in one file. Every map is
 * partial by design: enums are open (API Spec §12), and lookups go through the
 * helpers in `utils/` which fall back to a neutral treatment rather than
 * crashing.
 *
 * Colour is never the sole carrier of meaning (WCAG 1.4.1 / FDS §14.1), so
 * every entry pairs a `tone` with a `label` and, where relevant, an icon name.
 */

import type {
  ActivityCategory,
  KnownActivityCategory,
  KnownProviderStatus,
  KnownRiskFactorType,
  KnownRiskLevel,
  KnownSeverity,
  KnownTravelAdvisory,
  KnownWeatherCondition,
} from '@/types'

/** Semantic tone. Maps 1:1 onto the `--risk-*` token family. */
export const TONES = ['low', 'moderate', 'high', 'unknown'] as const
export type Tone = (typeof TONES)[number]

/** Lucide icon names. Resolved at the component boundary, not here. */
export type IconName = string

interface Descriptor {
  label: string
  tone: Tone
  icon: IconName
}

/** FDS §8.7 — RiskLevel. */
export const RISK_LEVEL_META: Record<KnownRiskLevel, Descriptor> = {
  low: { label: 'Low risk', tone: 'low', icon: 'check' },
  moderate: { label: 'Moderate risk', tone: 'moderate', icon: 'circle-alert' },
  high: { label: 'High risk', tone: 'high', icon: 'triangle-alert' },
}

/** FDS §8.7 — Severity of an individual risk factor. */
export const SEVERITY_META: Record<KnownSeverity, Descriptor> = {
  low: { label: 'Low', tone: 'low', icon: 'check' },
  moderate: { label: 'Moderate', tone: 'moderate', icon: 'circle-alert' },
  high: { label: 'High', tone: 'high', icon: 'triangle-alert' },
}

/** FDS §8.7 — TravelAdvisory. The per-day verdict; visible without expanding. */
export const TRAVEL_ADVISORY_META: Record<KnownTravelAdvisory, Descriptor> = {
  proceed: { label: 'Proceed', tone: 'low', icon: 'check' },
  caution: { label: 'Caution', tone: 'moderate', icon: 'circle-alert' },
  avoid: { label: 'Avoid', tone: 'high', icon: 'x' },
}

/** FDS §8.7 — ProviderStatus. Operator screens only. */
export const PROVIDER_STATUS_META: Record<KnownProviderStatus, Descriptor> = {
  available: { label: 'Available', tone: 'low', icon: 'check' },
  degraded: { label: 'Degraded', tone: 'moderate', icon: 'circle-alert' },
  unavailable: { label: 'Unavailable', tone: 'high', icon: 'x' },
}

/** FDS §8.7 — WeatherCondition. An unknown value falls back to a neutral cloud. */
export const WEATHER_CONDITION_META: Record<
  KnownWeatherCondition,
  { label: string; icon: IconName }
> = {
  clear: { label: 'Clear', icon: 'sun' },
  partly_cloudy: { label: 'Partly cloudy', icon: 'cloud-sun' },
  cloudy: { label: 'Cloudy', icon: 'cloud' },
  rain: { label: 'Rain', icon: 'cloud-rain' },
  heavy_rain: { label: 'Heavy rain', icon: 'cloud-rain-wind' },
  thunderstorm: { label: 'Thunderstorm', icon: 'cloud-lightning' },
  snow: { label: 'Snow', icon: 'snowflake' },
  fog: { label: 'Fog', icon: 'cloud-fog' },
}

export const FALLBACK_CONDITION_ICON: IconName = 'cloud'

/** FDS §8.5 — RiskFactorType. */
export const RISK_FACTOR_TYPE_META: Record<KnownRiskFactorType, { label: string; icon: IconName }> =
  {
    heat: { label: 'Heat', icon: 'thermometer-sun' },
    cold: { label: 'Cold', icon: 'thermometer-snowflake' },
    rain: { label: 'Rain', icon: 'cloud-rain' },
    storm: { label: 'Storm', icon: 'cloud-lightning' },
    wind: { label: 'Wind', icon: 'wind' },
  }

/**
 * FDS §6.4 — ActivityCategory.
 *
 * Known slugs get a friendly label; unknown ones are title-cased. The UI must
 * render whatever categories arrive and must not hardcode the three v1 values,
 * because new categories are additive (API Spec §12).
 */
export const ACTIVITY_CATEGORY_LABELS: Record<KnownActivityCategory, string> = {
  outdoor_sightseeing: 'Outdoor sightseeing',
  beach: 'Beach',
  indoor_museum: 'Indoor & museums',
}

/**
 * Ordering hint for activity bars. Categories not listed sort after these, in
 * the order the API returned them. `indoor_museum` sits alongside the outdoor
 * scores rather than below them: for a family planner a rainy day is not a
 * lost day, it is a museum day (FDS §2.2).
 */
export const ACTIVITY_CATEGORY_ORDER: ActivityCategory[] = [
  'outdoor_sightseeing',
  'beach',
  'indoor_museum',
]

/**
 * FDS §6.3 — travelConfidence thresholds.
 *
 * Confidence is shown in plain language; the raw decimal may appear as
 * secondary text but must never be the primary reading. Ordered high → low and
 * read as "first threshold met wins".
 */
export const CONFIDENCE_BANDS = [
  { min: 0.8, label: 'High confidence', tone: 'low' },
  { min: 0.55, label: 'Moderate confidence', tone: 'moderate' },
  { min: 0.3, label: 'Low confidence', tone: 'moderate' },
  { min: 0, label: 'Very low confidence', tone: 'high' },
] as const satisfies ReadonlyArray<{ min: number; label: string; tone: Tone }>

/** Packing groupings. Presentational only — the API returns a flat string list. */
export const PACKING_CATEGORIES = [
  { id: 'clothing', label: 'Clothing' },
  { id: 'footwear', label: 'Footwear' },
  { id: 'protection', label: 'Weather protection' },
  { id: 'gear', label: 'Gear & electronics' },
  { id: 'other', label: 'Other' },
] as const

export type PackingCategoryId = (typeof PACKING_CATEGORIES)[number]['id']
