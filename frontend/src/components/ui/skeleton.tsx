import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/**
 * Skeleton — FDS §6.6, §9.14.
 *
 * Shape-matched to the real content, never a spinner for a card region. The
 * shimmer becomes a static tint under reduced motion, which `motion-safe:`
 * handles at the CSS level so no JS branch is needed.
 *
 * `aria-hidden` because a skeleton has nothing to announce; the region that
 * contains it carries `aria-busy` instead.
 */
export function Skeleton({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden="true"
      className={cn('rounded-md bg-muted motion-safe:animate-pulse', className)}
      {...props}
    />
  )
}

/** A block of text lines, with a shortened last line so it reads as prose. */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-2', className)} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} className={cn('h-4', index === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}
