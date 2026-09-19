import { Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface SpinnerProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
  /** Accessible label. Set to null when an adjacent element already announces the wait. */
  label?: string | null
}

const SIZES = { sm: 'size-4', md: 'size-5', lg: 'size-8' } as const

/**
 * Spinner.
 *
 * Reserved for button-internal and inline use — **never for a whole region**
 * (FDS §9.14). A region gets a shape-matched skeleton instead, because a
 * spinner tells the user nothing about what is arriving, while a skeleton shows
 * them the shape of it and stops the layout jumping when it lands.
 */
export function Spinner({ className, size = 'md', label = 'Loading' }: SpinnerProps) {
  return (
    <span role={label ? 'status' : undefined} className="inline-flex items-center">
      <Loader2
        className={cn('animate-spin text-muted-foreground', SIZES[size], className)}
        aria-hidden="true"
      />
      {label ? <span className="sr-only">{label}</span> : null}
    </span>
  )
}
