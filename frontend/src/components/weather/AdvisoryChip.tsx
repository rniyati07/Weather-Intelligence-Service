import { Badge } from '@/components/ui/badge'
import type { TravelAdvisory } from '@/types'
import { formatAdvisory } from '@/utils/domain'
import { DomainIcon } from './DomainIcon'

export interface AdvisoryChipProps {
  advisory: TravelAdvisory
  className?: string
}

/**
 * The per-day verdict — `proceed` / `caution` / `avoid`.
 *
 * Shown on the timeline card *without* expanding it (FDS §6.4): the advisory is
 * the day's answer, and burying it behind an interaction would mean a user
 * scanning a 16-day trip has to open every card to find the bad days.
 *
 * Icon + text + colour, never colour alone. Shared by the timeline and the day
 * detail.
 */
export function AdvisoryChip({ advisory, className }: AdvisoryChipProps) {
  const { label, tone, icon } = formatAdvisory(advisory)

  return (
    <Badge tone={tone} icon={<DomainIcon name={icon} />} className={className}>
      {label}
    </Badge>
  )
}
