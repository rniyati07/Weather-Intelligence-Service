import type { ReactNode } from 'react'

import { Container } from '@/components/common/Container'
import { PageTitle } from '@/components/common/PageTitle'
import { cn } from '@/lib/utils'

export interface PageContainerProps {
  children: ReactNode
  /** Renders the page's single `<h1>`. Omit only when the page draws its own hero. */
  title?: ReactNode
  description?: ReactNode
  eyebrow?: ReactNode
  /** Right-aligned page-level controls. */
  actions?: ReactNode
  width?: 'content' | 'prose' | 'full'
  className?: string
}

/**
 * The wrapper every page uses.
 *
 * Owns vertical rhythm and the page heading, so top spacing and `<h1>`
 * treatment are identical on every route without each page re-deciding. A page
 * that needs a full-bleed hero passes `title={undefined}` and renders its own —
 * but still comes through here for the gutters.
 */
export function PageContainer({
  children,
  title,
  description,
  eyebrow,
  actions,
  width = 'content',
  className,
}: PageContainerProps) {
  return (
    <Container width={width} className={cn('py-10 md:py-14', className)}>
      {title ? (
        <PageTitle description={description} eyebrow={eyebrow} actions={actions} className="mb-10">
          {title}
        </PageTitle>
      ) : null}

      {children}
    </Container>
  )
}
