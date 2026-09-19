import { createContext } from 'react'

import type { TemperatureUnit } from '@/types'

export interface PreferencesContextValue {
  /** The API is metric-only, so this drives a client-side conversion. */
  temperatureUnit: TemperatureUnit
  setTemperatureUnit: (unit: TemperatureUnit) => void
  toggleTemperatureUnit: () => void

  /**
   * User override for reduced motion. Additive to the OS setting, never
   * subtractive: someone who asked their system for less motion does not get
   * animation back by leaving this off (FDS §11.9).
   */
  reducedMotion: boolean
  setReducedMotion: (enabled: boolean) => void
}

/**
 * Kept separate from the provider component for the same reason as
 * `theme-context`: React Fast Refresh only preserves state in modules that
 * export components exclusively.
 */
export const PreferencesContext = createContext<PreferencesContextValue | null>(null)
