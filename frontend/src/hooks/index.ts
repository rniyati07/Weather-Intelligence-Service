/**
 * Reusable behaviour. The bridge between `services/` and `features/`.
 *
 * Data-fetching hooks (`useIntelligence`, `useNarrative`, `useGeocoding`) are
 * deliberately absent in this phase and will live in `hooks/queries/` once the
 * API is wired up.
 */

export { useCopyToClipboard } from './useCopyToClipboard'
export { useDebounce, useDebouncedCallback } from './useDebounce'
export { useLocalStorage } from './useLocalStorage'
export { useBreakpoint, useIsMobile, useMediaQuery, usePrefersReducedMotion } from './useMediaQuery'
export { usePreferences } from './usePreferences'
export { useTheme } from './useTheme'
export { useWindowSize, type WindowSize } from './useWindowSize'
