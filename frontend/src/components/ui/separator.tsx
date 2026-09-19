import type { ComponentProps, ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface SeparatorProps extends Omit<ComponentProps<'div'>, 'children'> {
  orientation?: 'horizontal' | 'vertical'
  /** Optional centred label, e.g. the "Forecast horizon · 16 days" divider. */
  label?: ReactNode
}

/**
 * Divider.
 *
 * Purely decorative by default, so it is hidden from assistive tech — a
 * screen-reader user gains nothing from being told a line exists. With a
 * `label` it becomes a `<div role="separator">` carrying that text, which is
 * how the forecast-horizon divider in the date picker is built.
 */
export function Separator({
  className,
  orientation = 'horizontal',
  label,
  ...props
}: SeparatorProps) {
  if (label) {
    return (
      <div role="separator" className={cn('flex items-center gap-4', className)} {...props}>
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
        <span className="text-caption text-muted-foreground">{label}</span>
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
      </div>
    )
  }

  return (
    <div
      data-slot="separator"
      role="none"
      aria-hidden="true"
      className={cn(
        'shrink-0 bg-border',
        orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px',
        className,
      )}
      {...props}
    />
  )
}

/** Named export matching the FDS component inventory. */
export const Divider = Separator
