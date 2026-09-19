import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface SectionTitleProps {
  children: ReactNode
  /** Right-aligned supporting text or controls. */
  actions?: ReactNode
  /** Override the heading level when nesting demands it. Never skip a level. */
  as?: 'h2' | 'h3'
  /** Wire to the section's `aria-labelledby`. */
  id?: string | undefined
  className?: string
}

/** Section heading — the `<h2>` beneath a `PageTitle` (FDS §14.3). */
export function SectionTitle({
  children,
  actions,
  as: Heading = 'h2',
  id,
  className,
}: SectionTitleProps) {
  return (
    <div className={cn('flex items-baseline justify-between gap-4', className)}>
      <Heading
        id={id}
        className={cn('font-semibold text-heading', Heading === 'h2' ? 'text-h2' : 'text-h3')}
      >
        {children}
      </Heading>

      {actions ? (
        <div className="flex shrink-0 items-center gap-3 text-body-sm text-muted-foreground">
          {actions}
        </div>
      ) : null}
    </div>
  )
}
