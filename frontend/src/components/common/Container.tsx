import type { ComponentProps, ElementType } from 'react'

import { cn } from '@/lib/utils'

export interface ContainerProps extends ComponentProps<'div'> {
  /** Renders as a different element — `main`, `section`, `header` — for landmarks. */
  as?: ElementType
  /** `content` is the 1280px product width; `prose` caps body copy at ~70ch. */
  width?: 'content' | 'prose' | 'full'
}

const WIDTHS = {
  content: 'max-w-[80rem]',
  prose: 'max-w-[70ch]',
  full: 'max-w-none',
} as const

/**
 * Horizontal gutter and max width — FDS §9.5.
 *
 * Margins step 16 → 24 → 32 across the breakpoint bands. Every page goes
 * through this rather than setting its own padding, so the left edge of content
 * lines up across routes.
 */
export function Container({
  as: Component = 'div',
  width = 'content',
  className,
  ...props
}: ContainerProps) {
  return (
    <Component
      className={cn('mx-auto w-full px-4 md:px-6 lg:px-8', WIDTHS[width], className)}
      {...props}
    />
  )
}
