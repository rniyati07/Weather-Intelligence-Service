import { useId, type ReactNode } from 'react'

import { SectionTitle } from '@/components/common/SectionTitle'
import { cn } from '@/lib/utils'

export interface SectionContainerProps {
  children: ReactNode
  /** Section heading. When present the section is labelled by it for assistive tech. */
  title?: ReactNode
  /** Right-aligned supporting text or controls beside the heading. */
  actions?: ReactNode
  /** In-page anchor target, e.g. `summary`, `daily`, `packing` (FDS §4.1). */
  id?: string
  /** `aria-busy` while the region's data is in flight. */
  busy?: boolean
  className?: string
}

/**
 * A labelled region within a page.
 *
 * Two things it enforces that are easy to lose otherwise. First, consistent
 * `--space-12` gaps between sections, so vertical rhythm does not drift as
 * pages are added. Second, a real `<section>` with `aria-labelledby` pointing
 * at its heading — which is what makes the dashboard's regions navigable by
 * landmark instead of one undifferentiated wall of content.
 *
 * `busy` matters more here than it looks: each region loads independently, and
 * the AI Explanation in particular can still be pending — or failed — while
 * everything around it is complete and interactive.
 */
export function SectionContainer({
  children,
  title,
  actions,
  id,
  busy = false,
  className,
}: SectionContainerProps) {
  const generatedId = useId()
  const headingId = title ? `${id ?? generatedId}-heading` : undefined

  return (
    <section
      id={id}
      aria-labelledby={headingId}
      aria-busy={busy || undefined}
      // `scroll-mt` keeps an anchored section clear of the sticky header.
      className={cn('scroll-mt-24 not-first:mt-12', className)}
    >
      {title ? (
        <SectionTitle id={headingId} actions={actions} className="mb-6">
          {title}
        </SectionTitle>
      ) : null}

      {children}
    </section>
  )
}
