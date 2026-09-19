import { use } from 'react'

import { PreferencesContext, type PreferencesContextValue } from '@/context/preferences-context'

/**
 * Read and change display preferences.
 *
 * Throws outside a `PreferencesProvider` rather than falling back to a default:
 * a silent default would show Celsius to someone who chose Fahrenheit, which is
 * a wrong number on screen rather than an obvious wiring bug.
 */
export function usePreferences(): PreferencesContextValue {
  const context = use(PreferencesContext)

  if (!context) {
    throw new Error('usePreferences must be used within a <PreferencesProvider>.')
  }

  return context
}
