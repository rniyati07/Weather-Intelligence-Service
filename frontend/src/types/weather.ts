/** Weather and per-day intelligence — API Spec §9.4, §9.9. */

import type { IsoDate, Score, UnitInterval } from './common'
import type { Location, Period } from './location'
import type {
  ActivityCategory,
  RiskFactorType,
  RiskLevel,
  Severity,
  TravelAdvisory,
  WeatherCondition,
} from './enums'

/** API Spec §9.4.1. Units are metric and fixed in v1; °F is a client-side conversion. */
export interface DailySummary {
  tempMinC: number
  /** Always ≥ tempMinC. */
  tempMaxC: number
  /** 0.0–1.0. Rendered as a percentage. */
  precipitationProbability: UnitInterval
  windSpeedKph: number
  condition: WeatherCondition
}

/**
 * API Spec §9.4.3. The explainability anchor (NFR-1).
 *
 * `description` is the human-facing text and is always shown on expansion.
 * `rule` is the developer-facing id — available on demand, never primary
 * (FDS §8.5).
 */
export interface RiskFactor {
  type: RiskFactorType
  severity: Severity
  description: string
  rule: string
}

/** API Spec §9.4.2. `riskFactors` may legitimately be empty on a low-risk day. */
export interface RiskAssessment {
  overallRiskLevel: RiskLevel
  riskFactors: RiskFactor[]
}

/** API Spec §9.4.4. */
export interface ActivitySuitability {
  activity: ActivityCategory
  /** Integer 0–100. Higher is more suitable. */
  score: Score
}

/** API Spec §9.4. One entry per day in the requested range, ascending by date. */
export interface DailyIntelligence {
  date: IsoDate
  summary: DailySummary
  riskAssessment: RiskAssessment
  activitySuitability: ActivitySuitability[]
  packingRecommendations: string[]
  travelAdvisory: TravelAdvisory
}

/**
 * API Spec §9.9. Underlying normalized reading, without intelligence.
 *
 * `precipitationMm` and `humidity` are genuinely nullable — a provider may
 * simply not report them. They render as "—", never as `0` (FDS §6.5).
 */
export interface RawWeatherReading {
  date: IsoDate
  tempMinC: number
  tempMaxC: number
  precipitationProbability: UnitInterval
  precipitationMm?: number | null
  windSpeedKph: number
  /** 0.0–1.0 relative humidity, if available. */
  humidity?: UnitInterval | null
  condition: WeatherCondition
}

/** Payload of `GET /locations/{id}/weather/raw` — API Spec §8.4. */
export interface RawWeatherView {
  location: Location
  period: Period
  readings: RawWeatherReading[]
}
