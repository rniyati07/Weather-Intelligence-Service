/**
 * A search the user has run before — FDS §3.3, §15.7.
 *
 * Client-side only; the backend has no concept of it. Stored in `localStorage`
 * (last five, LRU) so a returning user can re-run a comparison in one tap. It
 * caches the *verdict* alongside the query because the landing page shows the
 * score and risk level without refetching — Marco (FDS §2.4) compares three
 * destinations for the same week, and making him re-query each one to remember
 * which won defeats the purpose.
 *
 * The cached verdict is a convenience, not a source of truth: opening a recent
 * search re-queries, and the fresh response wins.
 */

import type { IsoDate, IsoDateTime, LocationId, Score } from './common'
import type { RiskLevel } from './enums'

export interface RecentSearch {
  /** `"{lat},{lon}"` — the path parameter the query is re-run with. */
  locationId: LocationId
  /** Short display name, e.g. "Goa". */
  name: string
  /** Region and country, e.g. "Goa, India". Distinguishes same-named places. */
  context: string
  startDate: IsoDate
  endDate: IsoDate
  /** Verdict from the last run. Absent if that run never completed. */
  tripSuitabilityScore?: Score
  overallRiskLevel?: RiskLevel
  /** When the search was last run. Drives LRU eviction. */
  searchedAt: IsoDateTime
}
