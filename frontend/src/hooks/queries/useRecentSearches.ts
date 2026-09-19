import { MAX_RECENT_SEARCHES, STORAGE_KEYS } from '@/constants/storage'
import { readStorage, writeStorage } from '@/services/storage'
import type { RecentSearch } from '@/types'
import { useLocalStorage } from '../useLocalStorage'

/**
 * Recent searches — FDS §3.3, §15.7.
 *
 * Not a server query: this is `localStorage`, last five, LRU. It lives beside
 * the query hooks because it is the same kind of seam — the page asks for data
 * and does not know where it comes from.
 *
 * The cached verdict on each entry is a convenience, not a source of truth:
 * opening a recent search re-queries, and the fresh response wins.
 */
export function useRecentSearches(): RecentSearch[] {
  const [searches] = useLocalStorage<RecentSearch[]>(STORAGE_KEYS.recentSearches, [])

  // Guards against hand-edited or older-shaped data in storage.
  return Array.isArray(searches) ? searches : []
}

/**
 * Record a search that has just produced a verdict.
 *
 * A plain function rather than part of the hook, deliberately. It is called
 * from an effect once the dashboard's intelligence query resolves, and writing
 * straight to storage keeps that effect a pure external-system sync — no
 * `setState`, so no cascading render. The landing page reads the new value on
 * its next mount, which is the only moment it can be seen.
 */
export function recordRecentSearch(search: RecentSearch): void {
  const current = readStorage<RecentSearch[]>(STORAGE_KEYS.recentSearches, [])
  const existing = Array.isArray(current) ? current : []

  // Same destination *and* dates is the same search — re-running it moves the
  // entry to the top rather than adding a duplicate row.
  const withoutDuplicate = existing.filter(
    (entry) =>
      !(
        entry.locationId === search.locationId &&
        entry.startDate === search.startDate &&
        entry.endDate === search.endDate
      ),
  )

  writeStorage(
    STORAGE_KEYS.recentSearches,
    [search, ...withoutDuplicate].slice(0, MAX_RECENT_SEARCHES),
  )
}
