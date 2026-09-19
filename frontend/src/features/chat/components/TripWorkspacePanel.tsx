import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { SkeletonText } from '@/components/ui/skeleton'
import { buildTripPath } from '@/constants/routes'
import type { IsoDate, WeatherIntelligence } from '@/types'
import { defaultSelectedDate, toTripDays } from '../trip-intelligence'
import { DayDetailPanel } from './DayDetailPanel'
import { DayStrip } from './DayStrip'
import { TripOutlookPanel } from './TripOutlookPanel'

export interface TripWorkspacePanelProps {
  intelligence: WeatherIntelligence | null
  isPending: boolean
  isError: boolean
  onRetry: () => void
  locationId: string
  startDate: IsoDate
  endDate: IsoDate
  selectedDate: IsoDate | null
  onSelectDate: (date: IsoDate) => void
}

/**
 * The structured half of the workspace: outlook, best/watch-out, the day
 * strip and the selected day's detail.
 *
 * Purely presentational over the deterministic `GET .../intelligence` payload
 * its parent fetched — which is what keeps the sidebar's glance card and this
 * panel speaking about the same day, from one query rather than two.
 */
export function TripWorkspacePanel({
  intelligence,
  isPending,
  isError,
  onRetry,
  locationId,
  startDate,
  endDate,
  selectedDate,
  onSelectDate,
}: TripWorkspacePanelProps) {
  if (isPending) {
    return (
      <div
        className="rounded-lg border border-border bg-surface p-5"
        aria-label="Loading trip outlook"
      >
        <SkeletonText lines={4} />
      </div>
    )
  }

  // Scoped and recoverable rather than silent: the trip is still active and
  // the conversation still works, so the workspace states what is missing and
  // offers a retry instead of vanishing and taking the trip's identity with
  // it.
  if (isError || !intelligence) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-5">
        <p className="text-body-sm text-muted-foreground">
          Couldn’t load the trip outlook for these dates.
        </p>
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </div>
    )
  }

  const days = toTripDays(intelligence)
  const active = selectedDate ?? defaultSelectedDate(days, intelligence.tripSummary)
  const selected = days.find((entry) => entry.date === active)
  const byDate = new Map(days.map((entry) => [entry.date, entry.day]))

  return (
    <div className="flex min-w-0 flex-col gap-5">
      <TripOutlookPanel
        summary={intelligence.tripSummary}
        dayCount={days.length}
        bestDay={byDate.get(intelligence.tripSummary.bestDays[0] ?? '')}
        worstDay={byDate.get(intelligence.tripSummary.worstDays[0] ?? '')}
      />

      {days.length > 1 ? (
        <section aria-label="Your days" className="flex min-w-0 flex-col gap-3">
          <div className="flex items-baseline justify-between gap-4">
            <p className="text-caption font-semibold tracking-[0.12em] text-muted-foreground uppercase">
              Your days
            </p>
            <Link
              to={buildTripPath({ locationId, startDate, endDate })}
              className="inline-flex items-center gap-1 rounded-md text-body-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              View details
              <ChevronRight className="size-4" aria-hidden="true" />
            </Link>
          </div>

          <DayStrip days={days} selectedDate={active} onSelect={onSelectDate} />
        </section>
      ) : null}

      {selected ? <DayDetailPanel entry={selected} /> : null}
    </div>
  )
}
