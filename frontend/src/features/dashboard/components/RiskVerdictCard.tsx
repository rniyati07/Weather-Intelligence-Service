import { ShieldAlert } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { DomainIcon } from '@/components/weather/DomainIcon'
import type { RiskLevel } from '@/types'
import { formatRisk, TONE_CLASSES } from '@/utils/domain'
import { cn } from '@/lib/utils'
import { CardLabel } from './CardLabel'

export interface RiskVerdictCardProps {
  level: RiskLevel
  /** One line of supporting context. Derived from the rules, never from narration. */
  summary: string
  onClick?: () => void
}

/**
 * The headline verdict — FDS §6.3.
 *
 * This is the first thing a user reads, and it answers the product's actual
 * question: not "what will the weather be" but "should I go". Icon, text and
 * colour together, never colour alone; the left accent bar restates the tone
 * for anyone scanning the band peripherally.
 *
 * Clicking scrolls to the daily timeline — the natural follow-up to a bad
 * verdict is "which days".
 */
export function RiskVerdictCard({ level, summary, onClick }: RiskVerdictCardProps) {
  const { label, tone, icon } = formatRisk(level)

  return (
    <Card
      tone={tone}
      interactive={Boolean(onClick)}
      onClick={onClick}
      {...(onClick
        ? {
            role: 'button',
            tabIndex: 0,
            onKeyDown: (event: React.KeyboardEvent) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onClick()
              }
            },
          }
        : {})}
      className="flex h-full flex-col gap-3"
    >
      <CardLabel icon={ShieldAlert}>Verdict</CardLabel>

      <p className={cn('flex items-center gap-2.5 text-h2 font-bold', TONE_CLASSES[tone].text)}>
        <DomainIcon name={icon} className="size-6 shrink-0" />
        {/* "High risk" reads as a category; the verdict should read as a sentence. */}
        {label.replace(/ risk$/, '')} travel risk
      </p>

      <p className="text-body-sm text-muted-foreground">{summary}</p>
    </Card>
  )
}
