import { CalendarDays, MapPin, Pencil } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { buildPlanPath } from '@/constants/routes'
import type { Location, Period } from '@/types'
import { formatDateRange } from '@/utils/date'
import { formatCoordinates, formatLocation } from '@/utils/format'

export interface TripHeaderProps {
  location: Location
  period: Period
}

/**
 * Destination and dates — the page's single `<h1>`.
 *
 * `location.name` is nullable; when the geocoder returned nothing the heading
 * falls back to formatted coordinates rather than rendering an empty title
 * (FDS §8.8). The coordinates appear as a subtitle regardless, because the
 * `locationId` is what actually identifies the query.
 */
export function TripHeader({ location, period }: TripHeaderProps) {
  const name = formatLocation(location)
  const coordinates = formatCoordinates(location.latitude, location.longitude)

  return (
    <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
      <div className="flex flex-col gap-2">
        <h1 className="flex items-center gap-3 text-h1 font-bold text-heading">
          <MapPin className="size-7 shrink-0 text-primary" aria-hidden="true" />
          {name}
        </h1>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body text-muted-foreground">
          <span className="flex items-center gap-2">
            <CalendarDays className="size-4 shrink-0" aria-hidden="true" />
            {formatDateRange(period.startDate, period.endDate)}
          </span>
          <span aria-hidden="true" className="text-border-strong">
            ·
          </span>
          <span className="tabular">{coordinates}</span>
        </div>
      </div>

      {/* Re-querying the same destination should not mean re-entering it. */}
      <Button variant="secondary" size="md" asChild>
        <Link to={buildPlanPath(location.name ?? coordinates)}>
          <Pencil aria-hidden="true" />
          Edit dates
        </Link>
      </Button>
    </div>
  )
}
