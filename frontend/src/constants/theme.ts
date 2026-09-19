/**
 * Theme constants — the TypeScript view of `styles/tokens.css`.
 *
 * Only names and breakpoints live here, never colour values: a hex string in
 * TypeScript is a second source of truth that silently drifts from the CSS.
 * Anything that needs a colour reads a token through a class name.
 */

export const THEMES = ['dark', 'light'] as const
export type Theme = (typeof THEMES)[number]

/** Dark ships first (FDS §9.2); light is fully tokenised and one class away. */
export const DEFAULT_THEME: Theme = 'dark'

/** Class applied to <html>. Kept in sync with the `@custom-variant` in globals.css. */
export const THEME_CLASS: Record<Theme, string> = {
  dark: 'dark',
  light: 'light',
}

/**
 * Breakpoint minimums in pixels — FDS §9.5.
 *
 * Tailwind is mobile-first, so the unprefixed base *is* the `sm` band. These
 * numbers exist for JS-side media queries (`useMediaQuery`), where a component
 * genuinely needs to branch on layout rather than restyle.
 */
export const BREAKPOINTS = {
  /** < 640 — mobile. The base band; has no Tailwind prefix. */
  sm: 0,
  /** 640–1023 — tablet. */
  md: 640,
  /** 1024–1279 — laptop. */
  lg: 1024,
  /** ≥ 1280 — desktop. */
  xl: 1280,
} as const

export type Breakpoint = keyof typeof BREAKPOINTS

/** Minimum touch target, in pixels — WCAG / FDS §10.4. */
export const MIN_TOUCH_TARGET_PX = 44

/** Max content width, matching `--container-content`. */
export const MAX_CONTENT_WIDTH_PX = 1280
