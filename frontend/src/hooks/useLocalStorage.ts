import { useCallback, useEffect, useState } from 'react'

import { readStorage, removeStorage, writeStorage } from '@/services/storage'

/**
 * State that survives a reload, and stays in sync across tabs.
 *
 * The `storage` listener is the part that is easy to leave out and awkward to
 * add later: without it, changing units in one tab leaves every other tab
 * rendering the old preference until it is reloaded.
 *
 * @param key    A key from `constants/storage` — never a literal.
 * @param initial Used when nothing is stored, or when what is stored is corrupt.
 * @param ttlMs  Optional expiry. Reads past it return `initial`.
 */
export function useLocalStorage<T>(
  key: string,
  initial: T,
  ttlMs?: number,
): [T, (value: T | ((previous: T) => T)) => void, () => void] {
  const [value, setValue] = useState<T>(() => readStorage(key, initial))

  const set = useCallback(
    (next: T | ((previous: T) => T)) => {
      setValue((previous) => {
        const resolved = typeof next === 'function' ? (next as (p: T) => T)(previous) : next
        writeStorage(key, resolved, ttlMs)
        return resolved
      })
    },
    [key, ttlMs],
  )

  const reset = useCallback(() => {
    removeStorage(key)
    setValue(initial)
  }, [key, initial])

  // `storage` fires only in *other* tabs, so this cannot loop back on itself.
  useEffect(() => {
    function handleStorage(event: StorageEvent) {
      if (event.key !== key) return
      setValue(readStorage(key, initial))
    }

    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [key, initial])

  return [value, set, reset]
}
