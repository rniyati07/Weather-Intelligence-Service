import { CalendarCheck, CalendarX, CalendarRange } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { IsoDate } from '@/types'
import { formatDate } from '@/utils/date'
import { isSingleDayTrip } from '@/utils/domain'
import { CardLabel } from './CardLabel'

export interface BestWorstDaysProps {
  bestDays: IsoDate[]
  worstDays: IsoDate[]
  onSelectDay: (date: IsoDate) => void
}

/**
 * Best and worst days — FDS §6.3.
 *
 * The single most actionable output for anyone with flexible dates, which is
 * why it sits in the verdict band rather than below the timeline.
 *
 * Three behaviours the spec calls out explicitly, all of which are easy to get
 * wrong by rendering `[0]` and moving on:
 *
 *  · Both are **arrays**. Every entry renders, not just the first.
 *  · An empty array **hides its card** rather than rendering "none".
 *  · A single-day trip returns the same date as both best and worst, so the
 *    pair collapses into one "Your travel day" card instead of contradicting
 *    itself.
 */
export function BestWorstDays({ bestDays, worstDays, onSelectDay }: BestWorstDaysProps) {
  if (isSingleDayTrip(bestDays, worstDays)) {
    const only = bestDays[0]
    if (!only) return null

    return (
      <DayHighlightCard
        icon={CalendarRange}
        label="Your travel day"
        dates={[only]}
        tone="neutral"
        onSelectDay={onSelectDay}
      />
    )
  }

  const hasBest = bestDays.length > 0
  const hasWorst = worstDays.length > 0
  if (!hasBest && !hasWorst) return null

  return (
    <div className="flex h-full flex-col gap-4">
      {hasBest ? (
        <DayHighlightCard
          icon={CalendarCheck}
          label={bestDays.length > 1 ? 'Best days' : 'Best day'}
          dates={bestDays}
          tone="best"
          onSelectDay={onSelectDay}
        />
      ) : null}

      {hasWorst ? (
        <DayHighlightCard
          icon={CalendarX}
          label={worstDays.length > 1 ? 'Worst days' : 'Worst day'}
          dates={worstDays}
          tone="worst"
          onSelectDay={onSelectDay}
        />
      ) : null}
    </div>
  )
}

function DayHighlightCard({
  icon,
  label,
  dates,
  tone,
  onSelectDay,
}: {
  icon: LucideIcon
  label: string
  dates: IsoDate[]
  tone: 'best' | 'worst' | 'neutral'
  onSelectDay: (date: IsoDate) => void
}) {
  return (
    <Card
      padded={false}
      className={cn(
        'flex flex-1 flex-col gap-2 border-l-[3px] p-5',
        tone === 'best' && 'border-l-accent',
        tone === 'worst' && 'border-l-risk-high',
        tone === 'neutral' && 'border-l-primary',
      )}
    >
      <CardLabel icon={icon}>{label}</CardLabel>

      <ul className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {dates.map((date) => (
          <li key={date}>
            <button
              type="button"
              onClick={() => {
                onSelectDay(date)
              }}
              className={cn(
                'inline-flex min-h-11 items-center rounded-sm text-h3 font-bold underline-offset-4 hover:underline',
                'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
                tone === 'best' && 'text-accent',
                tone === 'worst' && 'text-risk-high',
                tone === 'neutral' && 'text-primary',
              )}
            >
              {formatDate(date, 'compact')}
              <span className="sr-only"> — open day detail</span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}
