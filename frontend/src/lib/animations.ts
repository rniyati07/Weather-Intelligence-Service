/**
 * Framer Motion presets — FDS §11.
 *
 * Variants rather than inline props, for two reasons: a shared vocabulary keeps
 * every entrance on the same timing, and `staggerChildren` only works when the
 * parent and children are variants on the same tree.
 *
 * Reduced motion is honoured in two places and both are required. CSS caps
 * transition durations globally (globals.css), but Framer Motion animates
 * inline styles that CSS cannot reach — so components pair these presets with
 * `usePrefersReducedMotion()` and swap in the `*Reduced` variants, which drop
 * translation and scale and keep opacity only. Information is never carried by
 * motion alone (§11.9).
 */

import type { Transition, Variants } from 'framer-motion'

import { DURATION, EASING, SLIDE_DISTANCE, STAGGER } from '@/constants/motion'

const ease = [...EASING.out] as [number, number, number, number]
const easeStandard = [...EASING.standard] as [number, number, number, number]

export const transitions = {
  instant: { duration: DURATION.instant, ease },
  fast: { duration: DURATION.fast, ease },
  base: { duration: DURATION.base, ease: easeStandard },
  slow: { duration: DURATION.slow, ease: easeStandard },
  count: { duration: DURATION.count, ease },
} as const satisfies Record<string, Transition>

/** Opacity only. The safe default and the reduced-motion substitute for everything below. */
export const fade: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: transitions.base },
  exit: { opacity: 0, transition: transitions.fast },
}

/** Rise into place. Used for cards and section entrances. */
export const slideUp: Variants = {
  hidden: { opacity: 0, y: SLIDE_DISTANCE },
  visible: { opacity: 1, y: 0, transition: transitions.base },
  exit: { opacity: 0, y: SLIDE_DISTANCE, transition: transitions.fast },
}

export const slideDown: Variants = {
  hidden: { opacity: 0, y: -SLIDE_DISTANCE },
  visible: { opacity: 1, y: 0, transition: transitions.base },
  exit: { opacity: 0, y: -SLIDE_DISTANCE, transition: transitions.fast },
}

/** Horizontal entrance, for sheets and carousels. */
export const slideInRight: Variants = {
  hidden: { opacity: 0, x: 24 },
  visible: { opacity: 1, x: 0, transition: transitions.base },
  exit: { opacity: 0, x: 24, transition: transitions.fast },
}

/** Modal entrance: `.98 → 1` with a fade (FDS §11.5). */
export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.98 },
  visible: { opacity: 1, scale: 1, transition: transitions.base },
  exit: { opacity: 0, scale: 0.98, transition: transitions.fast },
}

/** Backdrop behind a modal or sheet. */
export const overlayFade: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: transitions.fast },
  exit: { opacity: 0, transition: transitions.fast },
}

/** Route change: 200ms fade plus an 8px upward translate (FDS §11.7). */
export const pageTransition: Variants = {
  hidden: { opacity: 0, y: SLIDE_DISTANCE },
  visible: { opacity: 1, y: 0, transition: { duration: 0.2, ease } },
  exit: { opacity: 0, transition: { duration: 0.15, ease } },
}

/**
 * Stagger container.
 *
 * The interval is capped so a 16-day timeline finishes in the same 300ms a
 * 3-day one does — otherwise the longest trip, which needs the most scanning,
 * would be the slowest to become readable.
 */
export function staggerContainer(childCount = 1): Variants {
  const interval = childCount > 1 ? Math.min(STAGGER.interval, STAGGER.maxTotal / childCount) : 0

  return {
    hidden: {},
    visible: { transition: { staggerChildren: interval, delayChildren: 0 } },
    exit: {},
  }
}

/** The child of a `staggerContainer`. */
export const staggerItem: Variants = slideUp

/** Interactive card hover: lift by 1px (FDS §11.2). */
export const cardHover = {
  rest: { y: 0 },
  hover: { y: -1, transition: transitions.fast },
} as const satisfies Variants

/* -------------------------------------------------------------------------
 * Reduced-motion substitutes. Same variant names, opacity only, so a component
 * swaps the object and changes nothing else.
 * ---------------------------------------------------------------------- */

const reduced: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: DURATION.instant } },
  exit: { opacity: 0, transition: { duration: DURATION.instant } },
}

export const reducedMotionVariants = reduced

/**
 * Pick between a preset and its reduced-motion substitute.
 *
 * @example
 *   const reduce = usePrefersReducedMotion()
 *   <motion.div variants={withReducedMotion(slideUp, reduce)} />
 */
export function withReducedMotion(variants: Variants, prefersReduced: boolean): Variants {
  return prefersReduced ? reduced : variants
}
