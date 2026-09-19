/**
 * Motion tokens — FDS §11.1. Mirrors the CSS custom properties in
 * `styles/tokens.css`; this is the TypeScript half, consumed by Framer Motion.
 *
 * Durations are seconds because that is Framer Motion's unit. Nothing exceeds
 * 600ms: motion clarifies relationships, it never performs.
 */

export const DURATION = {
  /** Hover, focus. */
  instant: 0.1,
  /** Buttons, chips. */
  fast: 0.15,
  /** Cards, sheets. */
  base: 0.25,
  /** Page transitions, meters. */
  slow: 0.4,
  /** Score count-up. */
  count: 0.6,
} as const

/** Cubic-bezier control points, in Framer Motion's array form. */
export const EASING = {
  out: [0, 0, 0.2, 1],
  standard: [0.4, 0, 0.2, 1],
} as const

/** Timeline cards stagger in at 40ms intervals, capped at 300ms total (FDS §6.4). */
export const STAGGER = {
  interval: 0.04,
  maxTotal: 0.3,
} as const

/** Default vertical travel for slide/fade-up entrances, in pixels. */
export const SLIDE_DISTANCE = 8

/** Milliseconds a chip must be hovered before its tooltip appears (FDS §11.2). */
export const TOOLTIP_DELAY_MS = 400

/** Toasts auto-dismiss after this long; at most three stack (FDS §6.6). */
export const TOAST_DURATION_MS = 4000
