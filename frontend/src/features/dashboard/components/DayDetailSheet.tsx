import { ChevronLeft, ChevronRight, Droplets, Wind } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Modal, ModalContent } from '@/components/ui/modal'
import { AdvisoryChip } from '@/components/weather/AdvisoryChip'
import { RiskBadge } from '@/components/weather/RiskBadge'
import { WeatherIcon } from '@/components/weather/WeatherIcon'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { usePreferences } from '@/hooks/usePreferences'
import type { DailyIntelligence, IsoDate } from '@/types'
import { formatDate } from '@/utils/date'
import { formatPercent, formatTemperatureRange, formatWindSpeed } from '@/utils/format'
import { ActivityBars } from './ActivityBars'
import { RiskFactorList } from './RiskFactorList'

export interface DayDetailSheetProps {
  day: DailyIntelligence | null
  previousDate: IsoDate | null
  nextDate: IsoDate | null
  onNavigate: (date: IsoDate) => void
  onClose: () => void
}

/**
 * Why one day carries its rating — FDS §5.4.
 *
 * A projection of data the dashboard already holds; it issues no request of its
 * own.
 *
 * Presented as a centred dialog at `md` and above and a bottom sheet below.
 * The FDS specifies a full route at `sm`; a full-height sheet is used instead
 * because it is visually equivalent while keeping focus trapping and
 * restore-on-close, which a route transition would hand back to the browser.
 * Deep-linkability — the actual requirement — is preserved by the `?day=`
 * parameter the parent owns.
 */
export function DayDetailSheet({
  day,
  previousDate,
  nextDate,
  onNavigate,
  onClose,
}: DayDetailSheetProps) {
  const isMobile = useIsMobile()
  const { temperatureUnit } = usePreferences()

  if (!day) return null

  /* Stepping between days re-renders the sheet in place. When the button that
   * was just pressed becomes disabled — pressing "Next day" onto the last day —
   * the browser drops focus to `<body>`, stranding a keyboard user outside the
   * dialog they are still in. Moving focus to the dialog itself keeps them
   * inside it and lets a screen reader announce the day they landed on. */
  function goToDay(date: IsoDate) {
    onNavigate(date)
    requestAnimationFrame(() => {
      document.querySelector<HTMLElement>('[role="dialog"]')?.focus()
    })
  }

  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <ModalContent
        variant={isMobile ? 'bottom' : 'center'}
        className="max-w-2xl"
        /* Restore focus to the day card that opened this sheet — FDS §11.5,
         * §14.2. Radix's own restore does not survive here: closing clears the
         * `?day=` parameter, and the router re-render unmounts the dialog, so
         * the node Radix captured is no longer the one it hands focus back to
         * and focus falls to `<body>`.
         *
         * Preventing the default and doing it by date is independent of that
         * ordering; the frame's delay lets the card re-render first. */
        onCloseAutoFocus={(event) => {
          event.preventDefault()
          const { date } = day
          requestAnimationFrame(() => {
            document.querySelector<HTMLElement>(`[data-day-card="${date}"]`)?.focus()
          })
        }}
        title={formatDate(day.date, 'medium')}
        description={formatDate(day.date, 'weekdayLong')}
      >
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge level={day.riskAssessment.overallRiskLevel} />
            <AdvisoryChip advisory={day.travelAdvisory} />
          </div>

          <div className="flex flex-col gap-3 rounded-lg bg-muted/40 p-4">
            <WeatherIcon
              condition={day.summary.condition}
              withLabel
              className="text-body font-medium text-heading"
            />

            <dl className="flex flex-wrap items-center gap-x-6 gap-y-2 text-body-sm">
              <div className="flex items-center gap-2">
                <dt className="text-muted-foreground">Temperature</dt>
                <dd className="tabular font-medium text-foreground">
                  {formatTemperatureRange(
                    day.summary.tempMaxC,
                    day.summary.tempMinC,
                    temperatureUnit,
                  )}
                </dd>
              </div>

              <div className="flex items-center gap-2">
                <dt className="flex items-center gap-1.5 text-muted-foreground">
                  <Droplets className="size-4" aria-hidden="true" />
                  Precipitation
                </dt>
                <dd className="tabular font-medium text-foreground">
                  {formatPercent(day.summary.precipitationProbability)}
                </dd>
              </div>

              <div className="flex items-center gap-2">
                <dt className="flex items-center gap-1.5 text-muted-foreground">
                  <Wind className="size-4" aria-hidden="true" />
                  Wind
                </dt>
                <dd className="tabular font-medium text-foreground">
                  {formatWindSpeed(day.summary.windSpeedKph)}
                </dd>
              </div>
            </dl>
          </div>

          <section className="flex flex-col gap-3">
            <h3 className="text-h4 font-semibold text-heading">Why this rating</h3>
            <RiskFactorList factors={day.riskAssessment.riskFactors} />
          </section>

          <section className="flex flex-col gap-3">
            <h3 className="text-h4 font-semibold text-heading">Activity suitability</h3>
            <ActivityBars activities={day.activitySuitability} />
          </section>

          {day.packingRecommendations.length > 0 ? (
            <section className="flex flex-col gap-3">
              <h3 className="text-h4 font-semibold text-heading">Pack for this day</h3>
              <ul className="flex flex-wrap gap-2">
                {day.packingRecommendations.map((item) => (
                  <li
                    key={item}
                    className="rounded-full border border-border px-3 py-1.5 text-body-sm text-muted-foreground"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
            <Button
              variant="ghost"
              size="sm"
              disabled={!previousDate}
              onClick={() => {
                if (previousDate) goToDay(previousDate)
              }}
            >
              <ChevronLeft aria-hidden="true" />
              Previous day
            </Button>

            <Button
              variant="ghost"
              size="sm"
              disabled={!nextDate}
              onClick={() => {
                if (nextDate) goToDay(nextDate)
              }}
            >
              Next day
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </div>
      </ModalContent>
    </Modal>
  )
}
