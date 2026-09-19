import { cn } from '@/lib/utils'
import type { WeatherCondition } from '@/types'
import { formatCondition } from '@/utils/domain'
import { DomainIcon } from './DomainIcon'

export interface WeatherIconProps {
  condition: WeatherCondition
  className?: string
  /**
   * Render the condition name beside the icon. Without it the icon is
   * decorative and the caller must supply the label itself — an icon alone
   * never carries meaning (FDS §14.3).
   */
  withLabel?: boolean
}

/**
 * A normalized weather condition as an icon, optionally labelled.
 *
 * Used by the timeline cards, the day detail and the raw-readings table, which
 * is why it is shared rather than feature-local.
 *
 * An unrecognised condition falls back to a neutral cloud with the title-cased
 * raw value — a new backend condition must render, not crash (API Spec §12).
 */
export function WeatherIcon({ condition, className, withLabel = false }: WeatherIconProps) {
  const { label, icon } = formatCondition(condition)

  if (!withLabel) {
    return (
      <>
        <DomainIcon name={icon} className={cn('size-5 text-muted-foreground', className)} />
        <span className="sr-only">{label}</span>
      </>
    )
  }

  return (
    <span className={cn('flex items-center gap-2', className)}>
      <DomainIcon name={icon} className="size-5 shrink-0 text-muted-foreground" />
      <span>{label}</span>
    </span>
  )
}
