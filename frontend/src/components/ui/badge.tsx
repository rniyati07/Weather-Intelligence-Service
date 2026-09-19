import { Slot } from '@radix-ui/react-slot'
import type { VariantProps } from 'class-variance-authority'
import type { ComponentProps, ReactNode } from 'react'

import { cn } from '@/lib/utils'
import type { Tone } from '@/constants/domain'
import { TONE_CLASSES } from '@/utils/domain'
import { badgeVariants } from './variants'

export interface BadgeProps extends ComponentProps<'span'>, VariantProps<typeof badgeVariants> {
  /**
   * Semantic tone. When set it overrides `variant`, pairing the tone's text
   * colour with its tinted surface.
   */
  tone?: Tone
  /** Leading icon. Decorative here — the adjacent text carries the meaning. */
  icon?: ReactNode
  asChild?: boolean
}

/**
 * Badge / status chip — FDS §9.13.
 *
 * Always **icon + text**. The icon is not decoration: risk, advisory and
 * provider status must never be carried by colour alone (WCAG 1.4.1 /
 * FDS §14.1), which is why `icon` sits in the API rather than being left to
 * each call site to remember.
 */
export function Badge({ className, variant, tone, icon, asChild, children, ...props }: BadgeProps) {
  const Component = asChild ? Slot : 'span'

  return (
    <Component
      data-slot="badge"
      data-tone={tone}
      className={cn(
        badgeVariants({ variant: tone ? undefined : variant }),
        tone && cn(TONE_CLASSES[tone].text, TONE_CLASSES[tone].surface),
        className,
      )}
      {...props}
    >
      {icon ? <span aria-hidden="true">{icon}</span> : null}
      {children}
    </Component>
  )
}
