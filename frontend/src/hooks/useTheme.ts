import { use } from 'react'

import { ThemeContext, type ThemeContextValue } from '@/context/theme-context'

/**
 * Read and change the active theme.
 *
 * Throws outside a `ThemeProvider` rather than returning a silent default: a
 * missing provider is a wiring bug, and the failure should be loud at the point
 * of the mistake instead of showing up as a component that mysteriously never
 * changes theme.
 */
export function useTheme(): ThemeContextValue {
  const context = use(ThemeContext)

  if (!context) {
    throw new Error('useTheme must be used within a <ThemeProvider>.')
  }

  return context
}
