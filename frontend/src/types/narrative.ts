/** AI narration — API Spec §9.6, §9.10.  Contract notes: FDS Appendix B. */

import type { IsoDate, LanguageCode } from './common'
import type { Location, Period } from './location'

/**
 * API Spec §9.6.
 *
 * `summaryText` is **display-only**. Nothing in the UI may parse it to obtain a
 * value — every number, level and ranking comes from the structured payload
 * (FDS §6.4, §8.6). This is the rule that keeps the deterministic engine the
 * single source of truth.
 *
 * `fallbackUsed` is always `false` today: the Phase 8 refactor made narration
 * mandatory server-side, so a narration failure returns `503 SERVICE_DEGRADED`
 * rather than a `200` with a templated fallback. Treat it as a compatibility
 * field, not a UI branch (FDS Appendix B).
 */
export interface Narrative {
  generatedByLlm: boolean
  summaryText: string
  /** Model identifier. Hidden when null. */
  modelUsed?: string | null
  /** Always false in the current implementation. */
  fallbackUsed: boolean
}

/** Request body of `POST /locations/{id}/intelligence/narrative` — API Spec §9.10. */
export interface NarrativeRequest {
  startDate: IsoDate
  endDate: IsoDate
  /** Defaults to `"en"`. v1 accepts only `"en"`; anything else 400s. */
  language?: LanguageCode
}

/** Response payload of the narrative endpoint — API Spec §8.5. */
export interface NarrativeView {
  location: Location
  period: Period
  narrative: Narrative
}
