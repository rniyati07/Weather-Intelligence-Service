import { Gauge } from 'lucide-react'

import { Tooltip } from '@/components/ui/tooltip'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { RiskLevel, Score } from '@/types'
import { formatRisk } from '@/utils/domain'
import { CardLabel } from './CardLabel'

export interface TripScoreCardProps {
  score: Score
  /** Tints the arc to match the verdict, so the two cards agree at a glance. */
  riskLevel: RiskLevel
}

const RADIUS = 52
const STROKE = 8
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/**
 * Overall trip quality — FDS §6.3.
 *
 * A circular gauge at `md` and above; a horizontal bar below, because a circle
 * wastes vertical space on a phone where the verdict band is the entire first
 * screen.
 *
 * `role="meter"` with a full `aria-label`: a screen reader announces "Trip
 * suitability, 37 out of 100" rather than reading a bare number out of a
 * decorative SVG (FDS §14.3).
 */
export function TripScoreCard({ score, riskLevel }: TripScoreCardProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)))
  const { tone } = formatRisk(riskLevel)
  const dashOffset = CIRCUMFERENCE * (1 - clamped / 100)

  return (
    <Card className="flex h-full flex-col gap-4">
      <CardLabel icon={Gauge}>Trip suitability</CardLabel>

      <Tooltip content="How good this trip looks for typical activities, from the computed daily scores.">
        <div
          role="meter"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Trip suitability, ${String(clamped)} out of 100`}
          tabIndex={0}
          className="relative flex flex-1 items-center justify-center rounded-md focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          {/* Circular gauge — hidden from assistive tech; the wrapper carries
              the meter semantics and the text equivalent. */}
          <svg
            viewBox="0 0 128 128"
            aria-hidden="true"
            className="hidden size-32 -rotate-90 md:block"
          >
            <circle
              cx="64"
              cy="64"
              r={RADIUS}
              fill="none"
              strokeWidth={STROKE}
              className="stroke-muted"
            />
            <circle
              cx="64"
              cy="64"
              r={RADIUS}
              fill="none"
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={dashOffset}
              className={cn('transition-[stroke-dashoffset] duration-[600ms] ease-out', {
                'stroke-risk-low': tone === 'low',
                'stroke-risk-moderate': tone === 'moderate',
                'stroke-risk-high': tone === 'high',
                'stroke-risk-unknown': tone === 'unknown',
              })}
            />
          </svg>

          <p className="absolute hidden flex-col items-center md:flex">
            <span className="tabular text-metric-lg font-bold text-heading">{clamped}</span>
            <span className="text-caption text-muted-foreground">/ 100</span>
          </p>

          {/* Horizontal bar below `md`. */}
          <div className="flex w-full flex-col gap-2 md:hidden">
            <p className="flex items-baseline gap-1.5">
              <span className="tabular text-metric font-bold text-heading">{clamped}</span>
              <span className="text-body-sm text-muted-foreground">/ 100</span>
            </p>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn('h-full rounded-full transition-[width] duration-[600ms] ease-out', {
                  'bg-risk-low': tone === 'low',
                  'bg-risk-moderate': tone === 'moderate',
                  'bg-risk-high': tone === 'high',
                  'bg-risk-unknown': tone === 'unknown',
                })}
                style={{ width: `${String(clamped)}%` }}
              />
            </div>
          </div>
        </div>
      </Tooltip>
    </Card>
  )
}
