/** Trip-level rollups — API Spec §9.1, §9.5, §9.7, §9.8. */

import type { IsoDate, Score, UnitInterval } from './common'
import type { Location, Period } from './location'
import type { Narrative } from './narrative'
import type { RiskLevel } from './enums'
import type { DailyIntelligence } from './weather'

/**
 * API Spec §9.5.
 *
 * `bestDays` / `worstDays` are arrays: render every entry, not `[0]`. A
 * single-day trip returns the same date in both, which the UI collapses into
 * one combined card rather than a contradictory pair (FDS §6.3).
 */
export interface TripSummary {
  bestDays: IsoDate[]
  worstDays: IsoDate[]
  overallPackingList: string[]
  /** Worst-case risk across the trip. */
  overallRiskLevel: RiskLevel
  /** Integer 0–100. Overall trip quality for likely activities. */
  tripSuitabilityScore: Score
  /**
   * 0.0–1.0, from forecast horizon, source agreement and data completeness.
   * Displayed as plain language ("Moderate confidence"), never as a raw
   * decimal in the primary reading (FDS §6.3).
   */
  travelConfidence: UnitInterval
}

/**
 * Root payload of `GET /locations/{id}/intelligence` — API Spec §9.1.
 *
 * `narrative` is **always null here**. It is populated only by the separate
 * `POST .../intelligence/narrative` call, which the dashboard fires in
 * parallel and never awaits before painting (FDS §3.2).
 */
export interface WeatherIntelligence {
  location: Location
  period: Period
  /** Ascending by date, one entry per day in range. */
  dailyIntelligence: DailyIntelligence[]
  tripSummary: TripSummary
  narrative?: Narrative | null
}

/** Payload of `GET /locations/{id}/intelligence/best-days` — API Spec §9.7. */
export interface BestDaysView {
  location: Location
  period: Period
  bestDays: IsoDate[]
  worstDays: IsoDate[]
  overallRiskLevel: RiskLevel
}

/** Payload of `GET /locations/{id}/intelligence/packing` — API Spec §9.8. */
export interface PackingView {
  location: Location
  period: Period
  overallPackingList: string[]
}
