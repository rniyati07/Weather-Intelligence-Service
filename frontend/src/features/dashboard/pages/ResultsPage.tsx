import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'

import { Container } from '@/components/common/Container'
import { ErrorState } from '@/components/feedback/ErrorState'
import { EmptyState } from '@/components/feedback/EmptyState'
import { LoadingSkeleton } from '@/components/feedback/LoadingSkeleton'
import { SectionContainer } from '@/components/layout/SectionContainer'
import { QUERY_PARAMS, ROUTES } from '@/constants/routes'
import {
  recordRecentSearch,
  useIntelligence,
  useNarrative,
  useRawWeather,
  useResolvedPlace,
} from '@/hooks/queries'
import { getErrorPresentation } from '@/constants/error-copy'
import type { IsoDate, Location } from '@/types'
import { formatPlaceContext } from '@/utils/format'
import { AiExplanationPanel, type NarrativeStatus } from '../components/AiExplanationPanel'
import { BestWorstDays } from '../components/BestWorstDays'
import { DailyTimeline } from '../components/DailyTimeline'
import { DayDetailSheet } from '../components/DayDetailSheet'
import { MetadataStrip } from '../components/MetadataStrip'
import { PackingSection } from '../components/PackingSection'
import { RawReadingsSection } from '../components/RawReadingsSection'
import { RiskVerdictCard } from '../components/RiskVerdictCard'
import { TravelConfidenceCard } from '../components/TravelConfidenceCard'
import { TripHeader } from '../components/TripHeader'
import { TripScoreCard } from '../components/TripScoreCard'

/**
 * Deep-dive intelligence dashboard — `/trip/:locationId?start=&end=` (FDS
 * Revision 2 §4.1), also mounted at the pre-Revision-2 `/results?location=&
 * start=&end=` path so an old bookmark or shared link still resolves.
 *
 * **The reference view.** Chat (`/`, `/chat/:conversationId`) is the primary
 * experience now; this page is the opt-in "show me the full reasoning"
 * screen it links out to via a Trip Summary Card's "View full intelligence"
 * action. Its own content is otherwise unchanged from Revision 1: one
 * screen, not four — best-days, packing and daily intelligence are sections
 * of a single result, and splitting them across routes would cost either
 * four API calls or cross-route state.
 *
 * The load model is what has to be right: intelligence and narration are two
 * independent queries. The deterministic regions paint as soon as the first
 * resolves, and narration resolves separately and **can fail on its own** —
 * when it does the error stays inside the AI Explanation card and every other
 * region remains fully interactive.
 *
 * This page reads only from `hooks/queries`, so it never learns whether the
 * data came from a fixture or from the API.
 */
export function ResultsPage() {
  const navigate = useNavigate()
  const params = useParams<{ locationId?: string }>()
  const [searchParams, setSearchParams] = useSearchParams()

  // `/trip/:locationId` (current) takes the path param; `/results?location=`
  // (compat) falls back to the query param.
  const locationId = params.locationId ?? searchParams.get(QUERY_PARAMS.locationId)
  const startDate = searchParams.get(QUERY_PARAMS.startDate)
  const endDate = searchParams.get(QUERY_PARAMS.endDate)
  const openDayParam = searchParams.get('day')

  const hasQuery = Boolean(locationId && startDate && endDate)

  /* The URL fully determines what is fetched, so a shared link, a refresh and a
   * back-navigation all restore exactly the same view (FDS §15.2). */

  const intelligenceQuery = useIntelligence({ locationId, startDate, endDate })
  const result = intelligenceQuery.data

  // Fired in parallel — never awaited before the deterministic regions paint.
  const narrativeQuery = useNarrative({ locationId, startDate, endDate })

  // Lazy: only runs once the raw-readings disclosure is opened.
  const [readingsRequested, setReadingsRequested] = useState(false)
  const readingsQuery = useRawWeather(
    { locationId, startDate, endDate },
    { enabled: readingsRequested },
  )

  /* The backend returns `location.name: null` — it only ever received
   * coordinates, because geocoding is the client's job (API Spec §5). The name
   * the user actually searched for lives in the client's geocoding cache, so it
   * is merged back in here rather than by changing `TripHeader`, whose props
   * stay `{ location, period }`. Falls back to the API's name, then to
   * formatted coordinates (FDS §8.8). */
  const resolvedPlace = useResolvedPlace(locationId)
  const placeName = resolvedPlace?.name ?? null
  const placeContext = resolvedPlace ? formatPlaceContext(resolvedPlace) : ''

  /* Narration status, derived from the query rather than tracked separately.
   * `forcedFailure` previews the degraded path in development. */
  const [forcedFailure, setForcedFailure] = useState(false)

  const narrativeStatus: NarrativeStatus = forcedFailure
    ? 'failed'
    : narrativeQuery.isError
      ? 'failed'
      : narrativeQuery.isPending
        ? 'loading'
        : narrativeQuery.data
          ? 'ready'
          : 'idle'

  const requestNarrative = useCallback(() => {
    setForcedFailure(false)
    narrativeQuery.refetch()
  }, [narrativeQuery])

  /* Remember the search once it has actually produced a verdict. Writes
   * straight to storage rather than through state, so this stays a pure
   * external-system sync (FDS §15.7). */
  useEffect(() => {
    if (!result || !locationId) return

    const { period, tripSummary } = result.data
    recordRecentSearch({
      // Keyed by the id from the URL, so re-opening the row re-runs the same
      // query. The *name* comes from the geocoding cache rather than the
      // response, which carries `location.name: null` by design.
      locationId,
      name: placeName ?? result.data.location.name ?? locationId,
      context: placeContext,
      startDate: period.startDate,
      endDate: period.endDate,
      tripSuitabilityScore: tripSummary.tripSuitabilityScore,
      overallRiskLevel: tripSummary.overallRiskLevel,
      searchedAt: new Date().toISOString(),
    })
  }, [result, locationId, placeName, placeContext])

  /* --- Day detail: deep-linked via `?day=` ------------------------------- */

  const openDay = useCallback(
    (date: IsoDate | null) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current)
          if (date) next.set('day', date)
          else next.delete('day')
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  if (!hasQuery) {
    return (
      <Container className="py-16">
        <ErrorState
          headline="No trip to show"
          body="This link is missing a destination or dates. Start a new search to get a verdict."
          action={{ label: 'Plan a trip', onClick: () => void navigate(ROUTES.plan) }}
        />
      </Container>
    )
  }

  // A failed intelligence query means there is no verdict to show at all, so
  // this one is page-scoped — unlike a narration failure (FDS §13.3).
  if (intelligenceQuery.isError) {
    const presentation = getErrorPresentation(intelligenceQuery.error?.code)

    return (
      <Container className="py-16">
        <ErrorState
          headline={presentation.headline}
          body={presentation.body}
          requestId={intelligenceQuery.error?.requestId}
          action={{
            label: presentation.action ?? 'Try again',
            onClick: intelligenceQuery.refetch,
          }}
        />
      </Container>
    )
  }

  if (!result) {
    return (
      <Container className="py-10 md:py-14">
        <LoadingSkeleton variant="card" count={4} label="Loading your trip verdict" />
      </Container>
    )
  }

  const { data, metadata } = result
  const { dailyIntelligence, tripSummary, period } = data

  const location: Location = {
    ...data.location,
    name:
      data.location.name ??
      (placeName ? [placeName, resolvedPlace?.country].filter(Boolean).join(', ') : null),
  }

  if (dailyIntelligence.length === 0) {
    return (
      <Container className="py-16">
        <TripHeader location={location} period={period} />
        <EmptyState
          className="mt-10"
          headline="No forecast for these dates"
          body="We can forecast up to 16 days ahead. Try a nearer range."
          action={{ label: 'Adjust dates', onClick: () => void navigate(ROUTES.plan) }}
        />
      </Container>
    )
  }

  // `?day=` may name a date outside the range — a stale bookmark, or a hand-
  // edited URL. An unknown date simply leaves the sheet closed.
  const dayIndex = dailyIntelligence.findIndex((day) => day.date === openDayParam)
  const activeDay = dayIndex >= 0 ? (dailyIntelligence[dayIndex] ?? null) : null

  const worstDay = dailyIntelligence.find((day) => day.date === tripSummary.worstDays[0])
  const verdictSummary =
    worstDay?.riskAssessment.riskFactors[0]?.description ??
    'No single day dominates the assessment for this range.'

  return (
    <Container className="py-10 md:py-14">
      <a
        href="#daily"
        className="skip-link rounded-md bg-primary px-4 py-2 text-body-sm font-medium text-primary-foreground"
      >
        Skip to results
      </a>

      <TripHeader location={location} period={period} />

      {/* ① Verdict band — 4-up at xl, 2×2 at md, stacked below. */}
      <SectionContainer id="summary" className="mt-10">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <RiskVerdictCard
            level={tripSummary.overallRiskLevel}
            summary={verdictSummary}
            onClick={() => {
              document.querySelector('#daily')?.scrollIntoView({ block: 'start' })
            }}
          />
          <TripScoreCard
            score={tripSummary.tripSuitabilityScore}
            riskLevel={tripSummary.overallRiskLevel}
          />
          <TravelConfidenceCard confidence={tripSummary.travelConfidence} />
          <BestWorstDays
            bestDays={tripSummary.bestDays}
            worstDays={tripSummary.worstDays}
            onSelectDay={openDay}
          />
        </div>
      </SectionContainer>

      {/* ② AI Explanation — loads late, fails alone. */}
      <SectionContainer id="explanation">
        <AiExplanationPanel
          status={narrativeStatus}
          narrative={forcedFailure ? null : (narrativeQuery.data ?? null)}
          onRetry={requestNarrative}
          onPreviewFailure={() => {
            setForcedFailure(true)
          }}
        />
      </SectionContainer>

      {/* ③ Daily timeline */}
      <DailyTimeline
        days={dailyIntelligence}
        bestDays={tripSummary.bestDays}
        worstDays={tripSummary.worstDays}
        onOpenDay={openDay}
      />

      {/* ④ Packing */}
      <PackingSection
        items={tripSummary.overallPackingList}
        locationId={location.id}
        startDate={period.startDate}
        endDate={period.endDate}
      />

      {/* ⑤ Raw readings — collapsed, lazily loaded */}
      <div className="mt-12">
        <RawReadingsSection
          readings={readingsQuery.data ?? null}
          loading={readingsQuery.isPending}
          onExpand={() => {
            setReadingsRequested(true)
          }}
        />
      </div>

      <MetadataStrip metadata={metadata} />

      <DayDetailSheet
        day={activeDay}
        previousDate={dayIndex > 0 ? (dailyIntelligence[dayIndex - 1]?.date ?? null) : null}
        nextDate={
          dayIndex >= 0 && dayIndex < dailyIntelligence.length - 1
            ? (dailyIntelligence[dayIndex + 1]?.date ?? null)
            : null
        }
        onNavigate={openDay}
        onClose={() => {
          openDay(null)
        }}
      />
    </Container>
  )
}
