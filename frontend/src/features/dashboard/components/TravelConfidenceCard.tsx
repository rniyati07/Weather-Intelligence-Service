import { Compass } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { UnitInterval } from '@/types'
import { formatConfidence, formatConfidenceValue } from '@/utils/format'
import { CardLabel } from './CardLabel'

export interface TravelConfidenceCardProps {
  confidence: UnitInterval
}

/**
 * How much to trust the assessment — FDS §6.3.
 *
 * The rule this card exists to enforce: **confidence is plain language, not a
 * decimal.** `0.64` means nothing to a traveller; "Moderate confidence" does.
 * The raw value stays as secondary text because a sceptical user should be able
 * to find it — but a confident-looking UI over a low-confidence forecast is a
 * product failure, and a bare number invites exactly that misreading.
 */
export function TravelConfidenceCard({ confidence }: TravelConfidenceCardProps) {
  const { label, tone, value } = formatConfidence(confidence)
  const percent = Math.round((value ?? 0) * 100)

  return (
    <Card className="flex h-full flex-col gap-4">
      <CardLabel icon={Compass}>Travel confidence</CardLabel>

      <Tooltip content="Based on forecast horizon, agreement between sources, and how complete the underlying data is.">
        <div
          role="meter"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Travel confidence: ${label}`}
          tabIndex={0}
          className="flex flex-1 flex-col justify-center gap-3 rounded-md focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <p className="text-h3 font-bold text-heading">{label}</p>

          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn('h-full rounded-full transition-[width] duration-[400ms] ease-out', {
                'bg-risk-low': tone === 'low',
                'bg-risk-moderate': tone === 'moderate',
                'bg-risk-high': tone === 'high',
                'bg-risk-unknown': tone === 'unknown',
              })}
              style={{ width: `${String(percent)}%` }}
            />
          </div>

          <p className="tabular text-body-sm text-muted-foreground">
            {formatConfidenceValue(confidence)}
          </p>
        </div>
      </Tooltip>
    </Card>
  )
}
