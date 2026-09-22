import { useCallback, useEffect, useMemo, type ReactNode } from 'react'

import { DEFAULT_THEME, THEME_CLASS, THEMES, type Theme } from '@/constants/theme'
import { STORAGE_KEYS } from '@/constants/storage'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import { ThemeContext, type ThemeContextValue } from './theme-context'

function isTheme(value: unknown): value is Theme {
  return typeof value === 'string' && (THEMES as readonly string[]).includes(value)
}

/**
 * Theme state, applied to `<html>`.
 *
 * Light is the shipping default and `index.html` sets the class inline so the
 * first paint already matches — the alternative is a flash of the wrong
 * theme before React mounts, which looks like a bug either direction.
 *
 * The preference is stored rather than read from `prefers-color-scheme`,
 * because this product *chooses* dark rather than following the OS. Honouring
 * the system preference is a small change here once light mode ships (FDS §9.2).
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useLocalStorage<string>(STORAGE_KEYS.theme, DEFAULT_THEME)
  const theme: Theme = isTheme(stored) ? stored : DEFAULT_THEME

  useEffect(() => {
    const root = document.documentElement
    root.classList.remove(...Object.values(THEME_CLASS))
    root.classList.add(THEME_CLASS[theme])
    root.style.colorScheme = theme
  }, [theme])

  const setTheme = useCallback((next: Theme) => setStored(next), [setStored])
  const toggleTheme = useCallback(
    () => setStored((current) => (current === 'dark' ? 'light' : 'dark')),
    [setStored],
  )

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme],
  )

  return <ThemeContext value={value}>{children}</ThemeContext>
}
