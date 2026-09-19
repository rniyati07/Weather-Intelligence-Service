import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface SettingRowProps {
  title: ReactNode
  description: ReactNode
  /** The control. Receives `id`/`aria-describedby` wiring from the caller. */
  control: ReactNode
  /** Ties the description to the control for assistive tech. */
  descriptionId?: string
  className?: string
}

/**
 * One preference: what it is, what it does, and the control that changes it.
 *
 * Every row states its effect rather than just its name. "Reduced motion" alone
 * tells a user nothing about what will change; naming the consequence is what
 * makes the setting decidable without trying it.
 *
 * Stacks on mobile so neither the description nor the control gets squeezed.
 */
export function SettingRow({
  title,
  description,
  control,
  descriptionId,
  className,
}: SettingRowProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 py-5 first:pt-0 last:pb-0',
        'md:flex-row md:items-center md:justify-between md:gap-8',
        className,
      )}
    >
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-h4 font-semibold text-heading">{title}</p>
        <p id={descriptionId} className="max-w-[52ch] text-body-sm text-muted-foreground">
          {description}
        </p>
      </div>

      <div className="shrink-0">{control}</div>
    </div>
  )
}
