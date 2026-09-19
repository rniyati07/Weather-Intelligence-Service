import { SectionContainer } from '@/components/layout/SectionContainer'
import type { DailyIntelligence, IsoDate } from '@/types'
import { DayCard } from './DayCard'

export interface DailyTimelineProps {
  days: DailyIntelligence[]
  bestDays: IsoDate[]
  worstDays: IsoDate[]
  onOpenDay: (date: IsoDate) => void
}

/**
 * The whole range at a glance — FDS §6.4.
 *
 * A scroll-snap carousel below `lg` and a wrapping grid above, so up to sixteen
 * days stay visible on a desktop without horizontal scrolling.
 *
 * `role="list"` is restored explicitly: `display: flex` on a `<ul>` strips list
 * semantics in Safari + VoiceOver, which would cost a screen-reader user the
 * "16 items" announcement that makes the range navigable in the first place.
 */
export function DailyTimeline({ days, bestDays, worstDays, onOpenDay }: DailyTimelineProps) {
  const best = new Set(bestDays)
  const worst = new Set(worstDays)

  return (
    <SectionContainer
      id="daily"
      title="Daily timeline"
      actions={<span className="hidden md:inline">Per-day verdict across your dates</span>}
    >
      <ul
        role="list"
        // `auto-fill` rather than a fixed column count: a 3-day trip and a
        // 16-day trip both need to look deliberate, and the track minimum is
        // tuned so a typical 5-day range lands on one row at `lg`.
        className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 lg:mx-0 lg:grid lg:grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] lg:overflow-visible lg:px-0"
      >
        {days.map((day) => (
          // `shrink-0` while it is a carousel, or flex compresses every card to
          // fit the viewport instead of letting the row scroll.
          <li key={day.date} role="listitem" className="flex shrink-0 lg:min-w-0 lg:shrink">
            <DayCard
              day={day}
              isBest={best.has(day.date)}
              isWorst={worst.has(day.date)}
              onOpen={onOpenDay}
            />
          </li>
        ))}
      </ul>
    </SectionContainer>
  )
}
