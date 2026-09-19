/** Primitives shared across the contract and the app. */

/** ISO-8601 calendar date, `YYYY-MM-DD`. */
export type IsoDate = string

/** ISO-8601 datetime in UTC, e.g. `2026-07-21T10:00:00Z`. */
export type IsoDateTime = string

/**
 * Canonical location identifier. In v1 this is a coordinate pair `"{lat},{lon}"`
 * (API Spec §5) — resolving a place name to coordinates is the client's job.
 */
export type LocationId = string

/** Integer 0–100, higher is better. Used by suitability scores. */
export type Score = number

/** Float 0.0–1.0. Used by probabilities, humidity and travel confidence. */
export type UnitInterval = number

/** Temperature unit preference. The API is metric-only; conversion is client-side. */
export type TemperatureUnit = 'celsius' | 'fahrenheit'

/** Narration language. v1 accepts `en` only; anything else 400s. */
export type LanguageCode = 'en'

/**
 * A date range mid-selection.
 *
 * Both ends are nullable because a range is built in two clicks: `start` set
 * with `end` still null is the normal intermediate state, not an error. A range
 * is only submittable once both are present.
 */
export interface DateRange {
  start: IsoDate | null
  end: IsoDate | null
}
