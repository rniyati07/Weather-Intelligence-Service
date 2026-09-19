/**
 * Enum → presentation lookups.
 *
 * Every function here is total: an unrecognised enum value returns a neutral
 * descriptor with a title-cased label instead of `undefined`. That is not
 * defensive habit, it is the contract — API Spec §10 requires consumers to
 * treat enums as open and tolerate a value they have never seen (a new
 * `WeatherCondition`, a new `ActivityCategory`) without failing.
 *
 * These are lookups, not judgements. Nothing here decides a risk level; it
 * decides how the level the engine already computed should look.
 */

import {
  ACTIVITY_CATEGORY_LABELS,
  ACTIVITY_CATEGORY_ORDER,
  FALLBACK_CONDITION_ICON,
  PROVIDER_STATUS_META,
  RISK_FACTOR_TYPE_META,
  RISK_LEVEL_META,
  SEVERITY_META,
  TRAVEL_ADVISORY_META,
  WEATHER_CONDITION_META,
  type IconName,
  type Tone,
} from '@/constants/domain'
import { titleCaseSlug } from './format'
import type {
  ActivityCategory,
  ActivitySuitability,
  KnownActivityCategory,
  KnownProviderStatus,
  KnownRiskLevel,
  KnownSeverity,
  KnownTravelAdvisory,
  KnownWeatherCondition,
  ProviderStatus,
  RiskFactorType,
  RiskLevel,
  Severity,
  TravelAdvisory,
  WeatherCondition,
} from '@/types'

export interface ToneDescriptor {
  label: string
  tone: Tone
  icon: IconName
}

function lookupTone<K extends string>(
  map: Record<K, ToneDescriptor>,
  value: string,
): ToneDescriptor {
  return (
    (map as Record<string, ToneDescriptor | undefined>)[value] ?? {
      label: titleCaseSlug(value),
      tone: 'unknown',
      icon: 'circle-help',
    }
  )
}

/** `high` → "High risk", tone `high`, warning icon. Unknown → neutral chip. */
export function formatRisk(level: RiskLevel): ToneDescriptor {
  return lookupTone<KnownRiskLevel>(RISK_LEVEL_META, level)
}

export function formatSeverity(severity: Severity): ToneDescriptor {
  return lookupTone<KnownSeverity>(SEVERITY_META, severity)
}

/** `avoid` → "Avoid", tone `high`. The per-day verdict. */
export function formatAdvisory(advisory: TravelAdvisory): ToneDescriptor {
  return lookupTone<KnownTravelAdvisory>(TRAVEL_ADVISORY_META, advisory)
}

/** Operator screens only — a provider name never reaches a consumer screen. */
export function formatProviderStatus(status: ProviderStatus): ToneDescriptor {
  return lookupTone<KnownProviderStatus>(PROVIDER_STATUS_META, status)
}

/** `thunderstorm` → { label: "Thunderstorm", icon: "cloud-lightning" }. */
export function formatCondition(condition: WeatherCondition): { label: string; icon: IconName } {
  const meta = (
    WEATHER_CONDITION_META as Record<string, { label: string; icon: IconName } | undefined>
  )[condition]

  return meta ?? { label: titleCaseSlug(condition), icon: FALLBACK_CONDITION_ICON }
}

/** `storm` → { label: "Storm", icon: "cloud-lightning" }. */
export function formatRiskFactorType(type: RiskFactorType): { label: string; icon: IconName } {
  const meta = (
    RISK_FACTOR_TYPE_META as Record<string, { label: string; icon: IconName } | undefined>
  )[type]

  return meta ?? { label: titleCaseSlug(type), icon: 'circle-help' }
}

/** `indoor_museum` → "Indoor & museums"; an unknown slug is title-cased. */
export function formatActivity(activity: ActivityCategory): string {
  return (
    (ACTIVITY_CATEGORY_LABELS as Record<string, string | undefined>)[activity] ??
    titleCaseSlug(activity)
  )
}

/**
 * Order activity scores for display: the curated v1 categories first, then any
 * the backend added, in the order it returned them. Pure — returns a new array.
 */
export function sortActivities<T extends Pick<ActivitySuitability, 'activity'>>(
  activities: readonly T[],
): T[] {
  const rank = new Map<string, number>(
    ACTIVITY_CATEGORY_ORDER.map((activity, index) => [activity, index]),
  )
  const fallbackRank = ACTIVITY_CATEGORY_ORDER.length

  return [...activities].sort(
    (a, b) => (rank.get(a.activity) ?? fallbackRank) - (rank.get(b.activity) ?? fallbackRank),
  )
}

/** Tailwind class fragments for a tone. Colour is always paired with icon + text. */
export const TONE_CLASSES: Record<
  Tone,
  { text: string; surface: string; border: string; dot: string }
> = {
  low: {
    text: 'text-risk-low',
    surface: 'bg-risk-low-surface',
    border: 'border-risk-low',
    dot: 'bg-risk-low',
  },
  moderate: {
    text: 'text-risk-moderate',
    surface: 'bg-risk-moderate-surface',
    border: 'border-risk-moderate',
    dot: 'bg-risk-moderate',
  },
  high: {
    text: 'text-risk-high',
    surface: 'bg-risk-high-surface',
    border: 'border-risk-high',
    dot: 'bg-risk-high',
  },
  unknown: {
    text: 'text-risk-unknown',
    surface: 'bg-risk-unknown-surface',
    border: 'border-risk-unknown',
    dot: 'bg-risk-unknown',
  },
}

/** True when the same date is both the best and the worst day — a single-day trip. */
export function isSingleDayTrip(
  bestDays: readonly string[],
  worstDays: readonly string[],
): boolean {
  return (
    bestDays.length === 1 &&
    worstDays.length === 1 &&
    bestDays[0] !== undefined &&
    bestDays[0] === worstDays[0]
  )
}

/** Narrow an unknown enum value to a known member, for exhaustive switches. */
export function isKnown<T extends string>(values: readonly T[], value: string): value is T {
  return (values as readonly string[]).includes(value)
}

export type { KnownActivityCategory, KnownWeatherCondition }
