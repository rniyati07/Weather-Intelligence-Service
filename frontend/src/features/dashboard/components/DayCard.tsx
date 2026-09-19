import { Droplets, Star, Wind } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { AdvisoryChip } from '@/components/weather/AdvisoryChip'
import { WeatherIcon } from '@/components/weather/WeatherIcon'
import { usePreferences } from '@/hooks/usePreferences'
import { cn } from '@/lib/utils'
import type { DailyIntelligence } from '@/types'
import { formatDate } from '@/utils/date'
import { formatRisk, TONE_CLASSES } from '@/utils/domain'
import { formatPercent, formatTemperatureRange, formatWindSpeed } from '@/utils/format'

export interface DayCardProps {
  day: DailyIntelligence
  isBest: boolean
  isWorst: boolean
  onOpen: (date: string) => void
}

/**
 * One day's verdict — FDS §6.4.
 *
 * Scannable as a unit: the advisory is visible **without expanding**, because a
 * user scanning a 16-day trip should be able to spot the bad days without
 * opening sixteen cards.
 *
 * Wind is emphasised when a `wind` risk factor fired. For a trekker, wind is a
 * safety input rather than a comfort one, and the design calls for it to be
 * readable without expanding anything (FDS §2.5).
 */
export function DayCard({ day, isBest, isWorst, onOpen }: DayCardProps) {
  const { temperatureUnit } = usePreferences()
  const { tone } = formatRisk(day.riskAssessment.overallRiskLevel)

  const windFired = day.riskAssessment.riskFactors.some((factor) => factor.type === 'wind')
  const factorCount = day.riskAssessment.riskFactors.length

  return (
    <Card
      tone={tone}
      interactive
      padded={false}
      role="button"
      tabIndex={0}
      // Stable handle for the day-detail sheet to restore focus to on close
      // (FDS §14.2). Keyed by date rather than index so it survives a re-render.
      data-day-card={day.date}
      aria-label={`${formatDate(day.date, 'weekdayLong')} ${formatDate(day.date, 'compact')} — open day detail`}
      onClick={() => {
        onOpen(day.date)
      }}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(day.date)
        }
      }}
      // Fixed width while the timeline is a carousel; fills its grid cell once
      // the timeline becomes a grid at `lg`. Without the `lg:w-full` the card
      // overflows its column and clips the wind reading and factor count.
      className="flex h-full w-[15rem] shrink-0 snap-start flex-col gap-4 p-5 lg:w-full lg:shrink"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
        <div className="flex min-w-0 flex-col">
          <span className="text-body-sm text-muted-foreground">
            {formatDate(day.date, 'weekdayLong')}
          </span>
          <span className="text-h3 font-bold text-heading">{formatDate(day.date, 'compact')}</span>
        </div>

        {isBest ? (
          <Badge variant="accent" icon={<Star />} className="shrink-0">
            Best day
          </Badge>
        ) : null}
        {isWorst && !isBest ? (
          <Badge tone="high" className="shrink-0">
            Worst day
          </Badge>
        ) : null}
      </div>

      <WeatherIcon condition={day.summary.condition} withLabel className="text-body" />

      <dl className="flex flex-wrap items-center gap-x-4 gap-y-2 text-body-sm">
        <div className="flex items-center gap-1.5">
          <dt className="sr-only">Temperature</dt>
          <dd className="tabular text-foreground">
            {formatTemperatureRange(day.summary.tempMaxC, day.summary.tempMinC, temperatureUnit)}
          </dd>
        </div>

        <div className="flex items-center gap-1.5">
          <dt>
            <Droplets className="size-4 text-muted-foreground" aria-hidden="true" />
            <span className="sr-only">Chance of precipitation</span>
          </dt>
          <dd className="tabular text-muted-foreground">
            {formatPercent(day.summary.precipitationProbability)}
          </dd>
        </div>

        <div className="flex items-center gap-1.5">
          <dt>
            <Wind
              className={cn(
                'size-4',
                windFired ? TONE_CLASSES[tone].text : 'text-muted-foreground',
              )}
              aria-hidden="true"
            />
            <span className="sr-only">Wind speed</span>
          </dt>
          <dd
            className={cn(
              'tabular',
              windFired ? cn(TONE_CLASSES[tone].text, 'font-medium') : 'text-muted-foreground',
            )}
          >
            {formatWindSpeed(day.summary.windSpeedKph)}
          </dd>
        </div>
      </dl>

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1">
        <AdvisoryChip advisory={day.travelAdvisory} />

        {factorCount > 0 ? (
          <span className="text-caption text-muted-foreground">
            {factorCount} {factorCount === 1 ? 'factor' : 'factors'}
          </span>
        ) : null}
      </div>
    </Card>
  )
}
