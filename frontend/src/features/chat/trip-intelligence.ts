/**
 * Derivations over `GET /locations/{id}/intelligence` for the trip workspace.
 *
 * Everything here is a *projection* of fields the deterministic engine already
 * computed — a day is "best" because its date appears in
 * `tripSummary.bestDays`, never because this file compared two temperatures.
 * No verdict, ranking or level is invented; the rule stays the one the whole
 * product runs on (FDS §1.3.2).
 */

import type { DailyIntelligence, IsoDate, TripSummary, WeatherIntelligence } from '@/types'

/**
 * How a day reads at a glance in the day strip.
 *
 * `best`/`watch-out` come straight from `bestDays`/`worstDays` membership.
 * `caution` and `steady` are a relabelling of that day's own
 * `travelAdvisory` — not a second opinion about it.
 */
export type DayState = 'best' | 'watch-out' | 'caution' | 'steady'

export interface TripDay {
  date: IsoDate
  day: DailyIntelligence
  state: DayState
}

const DAY_STATE_LABELS: Record<DayState, string> = {
  best: 'Best day',
  'watch-out': 'Watch-out',
  caution: 'Take care',
  steady: 'Good day',
}

export function dayStateLabel(state: DayState): string {
  return DAY_STATE_LABELS[state]
}

function stateFor(day: DailyIntelligence, summary: TripSummary): DayState {
  if (summary.bestDays.includes(day.date)) return 'best'
  if (summary.worstDays.includes(day.date)) return 'watch-out'
  // A day the engine flagged but which is neither the trip's best nor its
  // worst still deserves a distinct cue — this reads `travelAdvisory`, it
  // does not re-derive it.
  if (day.travelAdvisory === 'avoid' || day.travelAdvisory === 'caution') return 'caution'
  return 'steady'
}

/** Every day of the trip, in the order the backend returned them, tagged with
 * the state the engine's own fields imply. Length follows the real trip. */
export function toTripDays(intelligence: WeatherIntelligence): TripDay[] {
  return intelligence.dailyIntelligence.map((day) => ({
    date: day.date,
    day,
    state: stateFor(day, intelligence.tripSummary),
  }))
}

/** The day a user most likely wants pre-selected: the engine's first best day,
 * else the first day of the trip. Never a computed "nicest" day. */
export function defaultSelectedDate(days: TripDay[], summary: TripSummary): IsoDate | null {
  const best = days.find((entry) => summary.bestDays.includes(entry.date))
  return best?.date ?? days[0]?.date ?? null
}

/**
 * The highest-scoring activity for a day, used as the day's short "what this
 * day is for" cue. Returns null when the backend sent no activity scores, so
 * the caller renders nothing rather than a placeholder.
 */
export function topActivity(day: DailyIntelligence) {
  if (day.activitySuitability.length === 0) return null
  return day.activitySuitability.reduce((best, candidate) =>
    candidate.score > best.score ? candidate : best,
  )
}

/**
 * The reasons the engine recorded for a day, most severe first. These are the
 * `description` strings authored by the rule engine — displayed verbatim, in
 * the same spirit as the dashboard's risk-factor list.
 */
const SEVERITY_ORDER: Record<string, number> = { high: 0, moderate: 1, low: 2 }

export function dayReasons(day: DailyIntelligence) {
  return [...day.riskAssessment.riskFactors].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3),
  )
}
