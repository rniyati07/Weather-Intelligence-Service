import { Backpack, Compass, ShieldAlert } from 'lucide-react'
import { Link } from 'react-router'

import { LoadingSkeleton } from '@/components/feedback/LoadingSkeleton'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { buildTripPath } from '@/constants/routes'
import { useIntelligence } from '@/hooks/queries'
import type { TripContextDestination } from '@/types'
import { formatDate, formatDateRange } from '@/utils/date'
import { formatRisk, isSingleDayTrip, TONE_CLASSES } from '@/utils/domain'
import { formatConfidence, formatList, formatScore } from '@/utils/format'
import { cn } from '@/lib/utils'

export interface TripSummaryCardProps {
  destination: TripContextDestination
  startDate: string
  endDate: string
}

/**
 * The compact structured summary — required, and required to stay compact
 * (master prompt, "Trip Summary": "Do NOT split into multiple large
 * widgets"). One card composing the dashboard's own verdict fields rather
 * than four separate cards.
 *
 * Sourced independently from `GET /locations/{locationId}/intelligence` —
 * never parsed from the assistant's reply text (FDS Revision 2 §3.2, §7.2).
 * `locationId` is built from `destination.latitude`/`longitude` at 4dp,
 * which is exactly the format the backend's `GeocodedPlace.location_id`
 * already emits — no translation layer needed between a chat-resolved
 * destination and this endpoint.
 */
export function TripSummaryCard({ destination, startDate, endDate }: TripSummaryCardProps) {
  const locationId = `${destination.latitude.toFixed(4)},${destination.longitude.toFixed(4)}`
  const { data, isPending, isError } = useIntelligence({ locationId, startDate, endDate })

  if (isPending) {
    return (
      <Card className="max-w-md">
        <LoadingSkeleton variant="card" count={1} label="Loading trip summary" />
      </Card>
    )
  }

  // Quiet, not alarming: the conversation itself already answered the
  // question in prose. This is a bonus structured view, and its absence is
  // not an error the user needs to see (master prompt, "Error Handling").
  if (isError || !data) return null

  const { tripSummary } = data.data
  const risk = formatRisk(tripSummary.overallRiskLevel)
  const confidence = formatConfidence(tripSummary.travelConfidence)
  const bestDay = tripSummary.bestDays[0]
  const worstDay = tripSummary.worstDays[0]
  const singleDay = isSingleDayTrip(tripSummary.bestDays, tripSummary.worstDays)
  const packing = tripSummary.overallPackingList

  return (
    <Card tone={risk.tone} className="flex max-w-md flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-h4 font-semibold text-heading">{destination.displayName}</p>
          <p className="text-body-sm text-muted-foreground">
            {formatDateRange(startDate, endDate)}
          </p>
        </div>
        <p className="tabular shrink-0 text-metric font-bold text-heading">
          {formatScore(tripSummary.tripSuitabilityScore)}
        </p>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 text-body-sm">
        <span
          className={cn(
            'inline-flex items-center gap-1.5 font-medium',
            TONE_CLASSES[risk.tone].text,
          )}
        >
          <ShieldAlert className="size-4 shrink-0" aria-hidden="true" />
          {risk.label}
        </span>
        <span className="inline-flex items-center gap-1.5 text-muted-foreground">
          <Compass className="size-4 shrink-0" aria-hidden="true" />
          {confidence.label}
        </span>
      </div>

      {singleDay && bestDay ? (
        <p className="border-t border-border pt-3 text-body-sm">
          <span className="text-muted-foreground">Travel day: </span>
          <span className="font-medium text-heading">{formatDate(bestDay, 'compact')}</span>
        </p>
      ) : bestDay || worstDay ? (
        <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-border pt-3 text-body-sm">
          {bestDay ? (
            <p>
              <span className="text-muted-foreground">Best: </span>
              <span className="font-medium text-heading">{formatDate(bestDay, 'compact')}</span>
            </p>
          ) : null}
          {worstDay ? (
            <p>
              <span className="text-muted-foreground">Toughest: </span>
              <span className="font-medium text-heading">{formatDate(worstDay, 'compact')}</span>
            </p>
          ) : null}
        </div>
      ) : null}

      {packing.length > 0 ? (
        <div className="flex items-start gap-2 border-t border-border pt-3 text-body-sm text-muted-foreground">
          <Backpack className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            {formatList(packing.slice(0, 4))}
            {packing.length > 4 ? ', and more' : ''}
          </p>
        </div>
      ) : null}

      <Button variant="secondary" size="sm" asChild className="self-start">
        <Link to={buildTripPath({ locationId, startDate, endDate })}>View full intelligence</Link>
      </Button>
    </Card>
  )
}
