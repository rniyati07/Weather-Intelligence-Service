import { createContext } from 'react'

import type { Theme } from '@/constants/theme'

export interface ThemeContextValue {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

/**
 * The context object lives in its own module, separate from the provider
 * component. React Fast Refresh can only preserve state in a module that
 * exports components exclusively — mixing a component and a plain value in one
 * file makes every theme edit blow away app state during development.
 */
export const ThemeContext = createContext<ThemeContextValue | null>(null)
