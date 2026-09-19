import type { VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'
import { TONE_CLASSES } from '@/utils/domain'
import type { Tone } from '@/constants/domain'
import { cardVariants } from './variants'

export interface CardProps extends ComponentProps<'div'>, VariantProps<typeof cardVariants> {
  /**
   * Applies the matching 3px left accent bar (FDS §9.6). Never the sole carrier
   * of meaning — the card's content still states the level in text.
   */
  tone?: Tone
}

/** Card — FDS §9.12. */
export function Card({ className, variant, interactive, padded, tone, ...props }: CardProps) {
  return (
    <div
      data-slot="card"
      data-tone={tone}
      className={cn(
        cardVariants({ variant, interactive, padded }),
        tone && cn('border-l-[3px]', TONE_CLASSES[tone].border),
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      data-slot="card-header"
      className={cn('flex items-center justify-between gap-3', className)}
      {...props}
    />
  )
}

export function CardTitle({ className, ...props }: ComponentProps<'h3'>) {
  return (
    <h3
      data-slot="card-title"
      className={cn('text-h3 font-semibold text-heading', className)}
      {...props}
    />
  )
}

/** Secondary line under a card title. Never the headline. */
export function CardDescription({ className, ...props }: ComponentProps<'p'>) {
  return (
    <p
      data-slot="card-description"
      className={cn('text-body-sm text-muted-foreground', className)}
      {...props}
    />
  )
}

export function CardContent({ className, ...props }: ComponentProps<'div'>) {
  return <div data-slot="card-content" className={cn('text-body', className)} {...props} />
}

export function CardFooter({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      data-slot="card-footer"
      className={cn('flex items-center gap-3 pt-4', className)}
      {...props}
    />
  )
}
