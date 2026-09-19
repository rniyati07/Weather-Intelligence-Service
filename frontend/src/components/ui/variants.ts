/**
 * `cva` definitions for the UI primitives.
 *
 * Separated from the components themselves for a practical reason: React Fast
 * Refresh can only preserve component state in a module that exports
 * components *exclusively*. Exporting `buttonVariants` alongside `Button`
 * silently downgrades every edit to that file into a full remount, which during
 * a styling pass means losing whatever state you were trying to look at.
 *
 * Every value below resolves to a semantic token. No hex, ever — the ESLint
 * config fails the build on one.
 */

import { cva } from 'class-variance-authority'

import { cn } from '@/lib/utils'

/** Button — FDS §9.10. Heights: sm 32 · md 40 · lg 48. */
export const buttonVariants = cva(
  cn(
    'inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-medium whitespace-nowrap',
    'transition-colors duration-150 ease-out outline-none',
    'focus-visible:ring-[3px] focus-visible:ring-ring/50',
    'disabled:pointer-events-none disabled:bg-muted disabled:text-subtle-foreground',
    "[&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4",
  ),
  {
    variants: {
      variant: {
        primary:
          'bg-primary text-primary-foreground hover:bg-primary-hover active:bg-primary-active',
        /** Highest-intent CTA. Used sparingly enough to stay meaningful. */
        accent: 'bg-accent text-accent-foreground hover:bg-accent-hover',
        secondary:
          'border border-border bg-surface text-primary hover:bg-primary-subtle active:bg-primary-subtle',
        ghost: 'text-muted-foreground hover:bg-muted hover:text-foreground',
        destructive: 'bg-destructive text-destructive-foreground hover:opacity-90',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        // 32px is the design's density (FDS §9.10), but §10.4 also mandates
        // 44px touch targets on mobile. Both hold: full target on a phone,
        // compact on a pointer device.
        sm: 'h-11 px-3 text-body-sm md:h-8',
        // 40px is the design's density; the same mobile rule applies as for `sm`.
        md: 'h-11 px-4 text-body md:h-10',
        lg: 'h-12 px-6 text-body-lg',
        // Square. Meets the 44px touch target only with surrounding padding.
        icon: 'size-11 md:size-10',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

/** Card — FDS §9.12. `ai` is the violet surface reserved for generated content. */
export const cardVariants = cva('rounded-lg border transition-shadow duration-150 ease-out', {
  variants: {
    variant: {
      default: 'border-border bg-surface shadow-sm',
      raised: 'border-border bg-surface-raised shadow-md',
      flat: 'border-border bg-surface shadow-none',
      ai: 'border-ai-border bg-ai-surface text-ai-foreground shadow-sm',
    },
    interactive: {
      true: cn(
        'cursor-pointer hover:shadow-md motion-safe:hover:-translate-y-px',
        'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
        'motion-safe:transition-[box-shadow,transform]',
      ),
      false: '',
    },
    padded: {
      true: 'p-6',
      false: '',
    },
  },
  defaultVariants: { variant: 'default', interactive: false, padded: true },
})

/** Badge / status chip — FDS §9.13. Always a pill, always icon + text. */
export const badgeVariants = cva(
  cn(
    'inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full text-caption font-medium',
    'px-2.5 py-1 whitespace-nowrap',
    "[&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-3.5",
  ),
  {
    variants: {
      variant: {
        neutral: 'bg-muted text-muted-foreground',
        outline: 'border border-border text-muted-foreground',
        primary: 'bg-primary-subtle text-primary',
        accent: 'bg-accent-subtle text-accent',
        ai: 'border border-ai-border bg-ai-surface text-ai-accent',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)
