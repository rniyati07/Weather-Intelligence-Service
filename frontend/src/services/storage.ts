/**
 * `localStorage` access, in one place.
 *
 * Components never touch `localStorage` directly. Three reasons, all of which
 * have bitten real apps: it throws in Safari private mode and inside sandboxed
 * iframes, it returns strings that `JSON.parse` will happily crash on, and
 * stale data written by an older build can be shaped nothing like what the
 * current code expects. Every read here fails soft to the caller's fallback.
 */

import { STORAGE_TTL_MS } from '@/constants/storage'

interface StoredRecord<T> {
  value: T
  /** Epoch ms. Absent means the entry never expires. */
  expiresAt?: number
}

function isAvailable(): boolean {
  try {
    const probe = '__wis_probe__'
    window.localStorage.setItem(probe, probe)
    window.localStorage.removeItem(probe)
    return true
  } catch {
    return false
  }
}

const available = typeof window !== 'undefined' && isAvailable()

/** Read a value, or the fallback if it is missing, corrupt or expired. */
export function readStorage<T>(key: string, fallback: T): T {
  if (!available) return fallback

  try {
    const raw = window.localStorage.getItem(key)
    if (raw === null) return fallback

    const record = JSON.parse(raw) as StoredRecord<T>

    if (record.expiresAt !== undefined && Date.now() > record.expiresAt) {
      window.localStorage.removeItem(key)
      return fallback
    }

    return record.value
  } catch {
    // Corrupt or foreign data. Discard rather than let it crash every mount.
    removeStorage(key)
    return fallback
  }
}

/** Write a value, optionally with a time-to-live. Silently no-ops if storage is unavailable. */
export function writeStorage<T>(key: string, value: T, ttlMs?: number): void {
  if (!available) return

  try {
    const record: StoredRecord<T> =
      ttlMs === undefined ? { value } : { value, expiresAt: Date.now() + ttlMs }
    window.localStorage.setItem(key, JSON.stringify(record))
  } catch {
    // Quota exceeded, or a private-mode write rejection. A failed cache write
    // is not worth interrupting the user for.
  }
}

export function removeStorage(key: string): void {
  if (!available) return
  try {
    window.localStorage.removeItem(key)
  } catch {
    /* nothing useful to do */
  }
}

/** Clear every key this app owns, leaving anything else on the origin intact. */
export function clearNamespace(prefix: string): void {
  if (!available) return

  try {
    const keys = Object.keys(window.localStorage).filter((key) => key.startsWith(prefix))
    keys.forEach((key) => window.localStorage.removeItem(key))
  } catch {
    /* nothing useful to do */
  }
}

/** Approximate bytes used by keys under a prefix — for the settings cache readout. */
export function measureNamespace(prefix: string): number {
  if (!available) return 0

  try {
    return Object.keys(window.localStorage)
      .filter((key) => key.startsWith(prefix))
      .reduce(
        (total, key) => total + key.length + (window.localStorage.getItem(key)?.length ?? 0),
        0,
      )
  } catch {
    return 0
  }
}

export const STORAGE_AVAILABLE = available
export { STORAGE_TTL_MS }
