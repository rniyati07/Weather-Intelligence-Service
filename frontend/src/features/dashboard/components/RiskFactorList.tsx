import { EmptyState } from '@/components/feedback/EmptyState'
import { Badge } from '@/components/ui/badge'
import { DomainIcon } from '@/components/weather/DomainIcon'
import { ShieldCheck } from 'lucide-react'

import type { RiskFactor } from '@/types'
import { formatRiskFactorType, formatSeverity } from '@/utils/domain'

export interface RiskFactorListProps {
  factors: RiskFactor[]
}

/**
 * Explainability made visible — FDS §6.4, §8.5.
 *
 * "The system said so" is never the answer. Every factor carries the human
 * `description`, always shown; the `rule` id that produced it is available in a
 * disclosure but never primary — it is a developer-facing anchor, and a
 * traveller reading "precip_prob_gt_high" has learned nothing.
 *
 * An empty list on a low-risk day is a **positive** outcome, not a blank
 * region — hence the reassuring empty state rather than a grey "nothing here".
 */
export function RiskFactorList({ factors }: RiskFactorListProps) {
  if (factors.length === 0) {
    return (
      <EmptyState
        variant="positive"
        icon={ShieldCheck}
        headline="No significant risks"
        body="Conditions look favourable for this day."
      />
    )
  }

  return (
    <ul className="flex flex-col gap-3">
      {factors.map((factor) => {
        const type = formatRiskFactorType(factor.type)
        const severity = formatSeverity(factor.severity)

        return (
          <li
            key={`${factor.type}-${factor.rule}`}
            className="flex flex-col gap-2 rounded-md border border-border p-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={severity.tone} icon={<DomainIcon name={type.icon} />}>
                {type.label}
              </Badge>
              <span className="text-caption text-muted-foreground">{severity.label} severity</span>
            </div>

            <p className="text-body text-foreground">{factor.description}</p>

            {/* Developer-facing, available on demand, never the headline. */}
            <details className="text-body-sm">
              <summary className="w-fit cursor-pointer rounded-sm text-muted-foreground hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
                Which rule fired?
              </summary>
              <code className="mt-2 inline-block rounded-sm bg-muted px-2 py-1 text-caption text-foreground">
                {factor.rule}
              </code>
            </details>
          </li>
        )
      })}
    </ul>
  )
}
