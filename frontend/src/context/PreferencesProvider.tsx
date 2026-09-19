import { useCallback, useEffect, useMemo, type ReactNode } from 'react'

import { STORAGE_KEYS } from '@/constants/storage'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import type { TemperatureUnit } from '@/types'
import { PreferencesContext, type PreferencesContextValue } from './preferences-context'

interface StoredPreferences {
  temperatureUnit: TemperatureUnit
  reducedMotion: boolean
}

const DEFAULTS: StoredPreferences = { temperatureUnit: 'celsius', reducedMotion: false }

function isUnit(value: unknown): value is TemperatureUnit {
  return value === 'celsius' || value === 'fahrenheit'
}

/**
 * Display preferences, persisted per device.
 *
 * Units live in global state rather than in the URL because they are a property
 * of the *reader*, not of the query — two people opening the same shared result
 * link should each see their own preferred unit. Everything defining the query
 * stays in the URL (FDS §15.2).
 *
 * Conversion is client-side (the API is metric and fixed in v1), so toggling
 * never triggers a refetch.
 *
 * Deliberately mirrors `ThemeProvider` rather than introducing a state library
 * for a couple of fields. If this grows past a handful of values, promote it to
 * the Zustand store the FDS anticipates.
 */
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useLocalStorage<StoredPreferences>(STORAGE_KEYS.preferences, DEFAULTS)

  // Guards against a stale or hand-edited value in localStorage.
  const temperatureUnit = isUnit(stored.temperatureUnit) ? stored.temperatureUnit : 'celsius'
  const reducedMotion = stored.reducedMotion === true

  const setTemperatureUnit = useCallback(
    (unit: TemperatureUnit) => {
      setStored((current) => ({ ...current, temperatureUnit: unit }))
    },
    [setStored],
  )

  const toggleTemperatureUnit = useCallback(() => {
    setStored((current) => ({
      ...current,
      temperatureUnit: current.temperatureUnit === 'celsius' ? 'fahrenheit' : 'celsius',
    }))
  }, [setStored])

  const setReducedMotion = useCallback(
    (enabled: boolean) => {
      setStored((current) => ({ ...current, reducedMotion: enabled }))
    },
    [setStored],
  )

  /* Reflected onto the document so CSS can act on it, the same way
   * `ThemeProvider` publishes the theme class. Styling is where motion actually
   * lives today, so this is what makes the toggle take effect rather than just
   * record an intention. */
  useEffect(() => {
    const root = document.documentElement
    if (reducedMotion) root.dataset.reducedMotion = 'reduce'
    else delete root.dataset.reducedMotion
  }, [reducedMotion])

  const value = useMemo<PreferencesContextValue>(
    () => ({
      temperatureUnit,
      setTemperatureUnit,
      toggleTemperatureUnit,
      reducedMotion,
      setReducedMotion,
    }),
    [temperatureUnit, setTemperatureUnit, toggleTemperatureUnit, reducedMotion, setReducedMotion],
  )

  return <PreferencesContext value={value}>{children}</PreferencesContext>
}
