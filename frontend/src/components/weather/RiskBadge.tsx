import { Badge } from '@/components/ui/badge'
import type { RiskLevel } from '@/types'
import { formatRisk } from '@/utils/domain'
import { DomainIcon } from './DomainIcon'

export interface RiskBadgeProps {
  level: RiskLevel
  className?: string
}

/**
 * Risk level as a status chip.
 *
 * Icon + text + colour, always all three — risk must never be carried by colour
 * alone (WCAG 1.4.1 / FDS §14.1). The icon is decorative; the label is what a
 * screen reader announces.
 *
 * An unrecognised level renders as a neutral chip showing the title-cased raw
 * value. That is not defensive habit: enums are open, and a new backend risk
 * level must degrade to something readable rather than crash the card it sits
 * in (API Spec §12 / FDS §6.3).
 */
export function RiskBadge({ level, className }: RiskBadgeProps) {
  const { label, tone, icon } = formatRisk(level)

  return (
    <Badge tone={tone} icon={<DomainIcon name={icon} />} className={className}>
      {label}
    </Badge>
  )
}
