import { WeatherIcon } from '@/components/weather/WeatherIcon'
import type { IsoDate } from '@/types'
import { formatDate } from '@/utils/date'
import { formatTemperature } from '@/utils/format'
import { cn } from '@/lib/utils'
import { dayStateLabel, type TripDay } from '../trip-intelligence'

export interface DayStripProps {
  days: TripDay[]
  selectedDate: IsoDate | null
  onSelect: (date: IsoDate) => void
}

const STATE_ACCENT: Record<TripDay['state'], string> = {
  best: 'text-risk-low',
  'watch-out': 'text-risk-high',
  caution: 'text-risk-moderate',
  steady: 'text-muted-foreground',
}

/**
 * The trip's days, in order, as a selectable strip — the reference's "your
 * days" row.
 *
 * One entry per day the backend actually returned, so a 2-day trip shows two
 * and a 9-day trip shows nine; nothing is padded to a fixed count. Each
 * entry's temperature, condition and state all come from that day's own
 * `dailyIntelligence` record.
 */
export function DayStrip({ days, selectedDate, onSelect }: DayStripProps) {
  if (days.length === 0) return null

  return (
    // `min-w-0` is what keeps the scroll *inside* this row: without it the
    // flex item sizes to its content and the overflow escapes to the page,
    // which shows up as a horizontally-scrolling document at 390px.
    <div
      role="tablist"
      aria-label="Days of your trip"
      className="-mx-1 flex w-full min-w-0 gap-2 overflow-x-auto px-1 pb-1"
    >
      {days.map((entry) => {
        const selected = entry.date === selectedDate
        return (
          <button
            key={entry.date}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => {
              onSelect(entry.date)
            }}
            className={cn(
              'min-w-[7.5rem] flex-1 rounded-lg border p-3 text-left transition-colors',
              'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
              selected
                ? 'border-primary/50 bg-primary-subtle'
                : 'border-border bg-surface hover:bg-muted',
            )}
          >
            <p className="text-caption text-muted-foreground">
              {formatDate(entry.date, 'weekdayLong')}
            </p>
            <p className="mt-0.5 text-body font-semibold text-heading">
              {formatDate(entry.date, 'compact')}
            </p>

            <WeatherIcon
              condition={entry.day.summary.condition}
              className="mt-2.5 size-5 text-muted-foreground"
            />

            <p className="tabular mt-2 text-h4 font-semibold text-heading">
              {formatTemperature(entry.day.summary.tempMaxC, 'celsius', { withUnit: false })}
            </p>
            <p className={cn('mt-0.5 text-caption font-medium', STATE_ACCENT[entry.state])}>
              {dayStateLabel(entry.state)}
            </p>
          </button>
        )
      })}
    </div>
  )
}
