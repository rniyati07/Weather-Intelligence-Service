import { CalendarDays, Sparkles, Tags } from 'lucide-react'

import type { TripContextPayload } from '@/types'
import { formatDateRange } from '@/utils/date'
import { titleCaseSlug } from '@/utils/format'
import { TripContextPopover } from './TripContextPopover'

export interface TripIdentityHeaderProps {
  trip: TripContextPayload
}

/**
 * The workspace's identity band: whose trip this is, at a glance.
 *
 * Every value is read from the conversation's own `tripContext` — the
 * destination name the backend geocoded, the dates it validated, the
 * interests it extracted. Nothing is derived from the assistant's prose, and
 * a field the backend hasn't established simply doesn't render (no "—"
 * placeholders, no empty rows).
 */
export function TripIdentityHeader({ trip }: TripIdentityHeaderProps) {
  const destination = trip.destination
  if (!destination) return null

  const interests = trip.interests ?? []

  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4 px-5 pt-6 pb-5 md:px-8 md:pt-8">
      <div className="min-w-0">
        <p className="flex items-center gap-2 text-caption font-semibold tracking-[0.14em] text-primary uppercase">
          <Sparkles className="size-3.5" aria-hidden="true" />
          Trip intelligence
        </p>

        <h1 className="mt-2 truncate text-h1 font-bold text-heading">{destination.displayName}</h1>

        <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-body-sm text-muted-foreground">
          {trip.startDate && trip.endDate ? (
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="size-4 shrink-0" aria-hidden="true" />
              {formatDateRange(trip.startDate, trip.endDate)}
            </span>
          ) : null}

          {interests.length > 0 ? (
            <span className="inline-flex items-center gap-1.5">
              <Tags className="size-4 shrink-0" aria-hidden="true" />
              {interests.map(titleCaseSlug).join(' · ')}
            </span>
          ) : null}
        </div>
      </div>

      <TripContextPopover trip={trip} />
    </header>
  )
}
