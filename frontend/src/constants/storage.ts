/**
 * localStorage keys — FDS §15.7.
 *
 * Namespaced and versioned. The version suffix means a shape change is a
 * rename, not a migration: old data is simply never read, and the app starts
 * from a clean default instead of crashing on a stale structure.
 */

const NS = 'wis'
const V = 'v1'

const key = (name: string) => `${NS}:${V}:${name}`

export const STORAGE_KEYS = {
  /** 'dark' | 'light'. Indefinite. */
  theme: key('theme'),
  /** Units, language, reduced-motion override. Indefinite. */
  preferences: key('preferences'),
  /** Last 5 searches, LRU. Indefinite. */
  recentSearches: key('recent-searches'),
  /** Geocoding results cache. 7 days. */
  geocodeCache: key('geocode-cache'),
  /** Packing checkbox state, keyed by (location, dates). 30 days. */
  packingChecklist: key('packing'),
} as const

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS]

/** Landing keeps at most this many recent searches (FDS §15.7). */
export const MAX_RECENT_SEARCHES = 5

/** Retention windows in milliseconds. */
export const STORAGE_TTL_MS = {
  geocodeCache: 7 * 24 * 60 * 60 * 1000,
  packingChecklist: 30 * 24 * 60 * 60 * 1000,
} as const
