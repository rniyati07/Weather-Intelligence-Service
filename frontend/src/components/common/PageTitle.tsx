import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface PageTitleProps {
  children: ReactNode
  /** Supporting line beneath the title. */
  description?: ReactNode
  /** Small label above the title, e.g. a breadcrumb or category. */
  eyebrow?: ReactNode
  /** Right-aligned controls, e.g. "Edit dates". */
  actions?: ReactNode
  className?: string
}

/**
 * The one `<h1>` on a page — FDS §14.3.
 *
 * Exactly one per page and heading levels never skipped, which is easier to
 * guarantee with a dedicated component than with a convention nobody
 * remembers. `SectionTitle` renders the `<h2>` below it.
 */
export function PageTitle({ children, description, eyebrow, actions, className }: PageTitleProps) {
  return (
    <div
      className={cn('flex flex-col gap-4 md:flex-row md:items-end md:justify-between', className)}
    >
      <div className="flex flex-col gap-2">
        {eyebrow ? (
          <p className="text-caption tracking-wide text-muted-foreground uppercase">{eyebrow}</p>
        ) : null}

        <h1 className="text-h1 font-bold text-heading">{children}</h1>

        {description ? (
          <p className="max-w-[70ch] text-body-lg text-muted-foreground">{description}</p>
        ) : null}
      </div>

      {actions ? <div className="flex shrink-0 items-center gap-3">{actions}</div> : null}
    </div>
  )
}
