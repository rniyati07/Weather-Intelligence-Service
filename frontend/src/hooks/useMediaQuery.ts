import { useSyncExternalStore } from 'react'

import { BREAKPOINTS, type Breakpoint } from '@/constants/theme'

/**
 * Subscribe to a media query.
 *
 * `useSyncExternalStore` rather than `useState` + `useEffect`: it reads the
 * match during render, so there is no first paint at the wrong breakpoint and
 * no layout flash when a component branches on size.
 *
 * Use this only where a component genuinely *renders differently* — a modal at
 * `md` and a full route at `sm`, say. Anything that is merely restyled belongs
 * in Tailwind's responsive variants, which cost nothing at runtime.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    () => window.matchMedia(query).matches,
    // Server snapshot. Nothing is rendered on a server today, but a mismatched
    // default here is the classic source of a hydration warning later.
    () => false,
  )
}

/** True at or above a named breakpoint. `useBreakpoint('lg')` → ≥1024px. */
export function useBreakpoint(breakpoint: Breakpoint): boolean {
  return useMediaQuery(`(min-width: ${String(BREAKPOINTS[breakpoint])}px)`)
}

/** True below `md` — the mobile band, where layout genuinely changes shape. */
export function useIsMobile(): boolean {
  return !useBreakpoint('md')
}

/**
 * The user's OS-level motion preference (FDS §11.9).
 *
 * CSS caps transition durations globally, but Framer Motion animates inline
 * styles that CSS cannot reach — so JS-driven motion has to consult this and
 * swap in the reduced variants. Information is never carried by motion alone.
 */
export function usePrefersReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)')
}
