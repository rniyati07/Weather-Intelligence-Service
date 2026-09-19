import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { PageContainer } from '@/components/layout/PageContainer'
import { QUERY_PARAMS, buildResultsPath } from '@/constants/routes'
import type { DateRange, GeocodedPlace } from '@/types'
import { isCompleteRange, resolvePreset } from '@/utils/calendar'
import { DestinationPicker } from '../components/DestinationPicker'
import { TripDatesPanel } from '../components/TripDatesPanel'

/**
 * Plan — `/plan`.
 *
 * Resolves a destination and a valid date range, then hands both to the
 * dashboard as URL parameters — which is what makes the result shareable and
 * refresh-stable (FDS §15.2).
 *
 * Validation lives entirely on this screen. The picker cannot express a range
 * outside the 16-day horizon and a reversed selection swaps, so a user should
 * never see a `400 VALIDATION_ERROR` from normal interaction. If they do, the
 * client-side guard has a bug (FDS §5.2).
 *
 * ⚠️ Geocoding is mocked. Only `data/planner.mock.ts` changes when the real
 * provider lands.
 */
export function PlannerPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Seeded from the landing page's search box, which passes a name rather than
  // a resolved place — resolution is this screen's job.
  const initialQuery = searchParams.get(QUERY_PARAMS.query) ?? ''

  const [place, setPlace] = useState<GeocodedPlace | null>(null)
  const [range, setRange] = useState<DateRange>(
    () => resolvePreset('weekend') ?? { start: null, end: null },
  )

  function handleSubmit() {
    if (!place || !isCompleteRange(range)) return

    void navigate(
      buildResultsPath({ locationId: place.id, startDate: range.start, endDate: range.end }),
    )
  }

  return (
    <PageContainer
      title="Plan a trip"
      description="Choose where and when. We'll compute the verdict, not just the weather."
    >
      <div className="grid gap-12 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-16">
        <DestinationPicker initialQuery={initialQuery} selected={place} onSelect={setPlace} />

        <TripDatesPanel
          value={range}
          onChange={setRange}
          onSubmit={handleSubmit}
          submitBlockedReason={place ? null : 'Choose a destination to continue.'}
        />
      </div>
    </PageContainer>
  )
}
