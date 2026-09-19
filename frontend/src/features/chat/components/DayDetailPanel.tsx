import { Droplets, Thermometer, Wind } from 'lucide-react'

import { WeatherIcon } from '@/components/weather/WeatherIcon'
import { formatDate } from '@/utils/date'
import { formatActivity, formatAdvisory, formatCondition, TONE_CLASSES } from '@/utils/domain'
import { formatPercent, formatTemperature, formatWindSpeed } from '@/utils/format'
import { cn } from '@/lib/utils'
import { dayReasons, dayStateLabel, topActivity, type TripDay } from '../trip-intelligence'

export interface DayDetailPanelProps {
  entry: TripDay
}

/**
 * The selected day, explained — the reference's day-detail band plus its "why
 * this recommendation" row.
 *
 * Every line is a field the engine produced: the advisory, the risk-factor
 * descriptions (verbatim, with their rule ids available as the tooltip-free
 * secondary text), the activity scores and the day's own packing list. The
 * component authors no guidance of its own.
 */
export function DayDetailPanel({ entry }: DayDetailPanelProps) {
  const { day } = entry
  const advisory = formatAdvisory(day.travelAdvisory)
  const condition = formatCondition(day.summary.condition)
  const reasons = dayReasons(day)
  const best = topActivity(day)

  return (
    <section
      className="rounded-lg border border-border bg-surface p-5"
      aria-label={`Details for ${formatDate(entry.date, 'medium')}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="text-caption font-semibold tracking-[0.1em] text-muted-foreground uppercase">
            {formatDate(entry.date, 'weekdayLong')} · {dayStateLabel(entry.state)}
          </p>
          <h3 className="mt-1 text-h4 font-semibold text-heading">
            {formatDate(entry.date, 'medium')} — {condition.label}
          </h3>
          {best ? (
            <p className="mt-1 text-body-sm text-muted-foreground">
              Best suited to{' '}
              <span className="text-foreground">{formatActivity(best.activity).toLowerCase()}</span>{' '}
              ({best.score}/100)
            </p>
          ) : null}
        </div>

        <span
          className={cn(
            'inline-flex items-center gap-2 rounded-md px-2.5 py-1 text-body-sm font-medium',
            TONE_CLASSES[advisory.tone].surface,
            TONE_CLASSES[advisory.tone].text,
          )}
        >
          <WeatherIcon condition={day.summary.condition} className="size-4" />
          {advisory.label}
        </span>
      </div>

      {reasons.length > 0 ? (
        <ul className="mt-4 flex flex-col gap-1.5 border-t border-border pt-4">
          {reasons.map((factor) => (
            <li key={factor.rule} className="flex gap-2 text-body-sm text-foreground">
              <span
                className={cn(
                  'mt-1.5 size-1.5 shrink-0 rounded-full',
                  TONE_CLASSES[factor.severity === 'high' ? 'high' : 'moderate'].dot,
                )}
                aria-hidden="true"
              />
              {factor.description}
            </li>
          ))}
        </ul>
      ) : null}

      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-border pt-3 text-body-sm text-muted-foreground">
        <div className="inline-flex items-center gap-1.5">
          <Droplets className="size-4 shrink-0" aria-hidden="true" />
          <dt className="sr-only">Chance of rain</dt>
          <dd className="tabular">{formatPercent(day.summary.precipitationProbability)} rain</dd>
        </div>
        <div className="inline-flex items-center gap-1.5">
          <Wind className="size-4 shrink-0" aria-hidden="true" />
          <dt className="sr-only">Wind speed</dt>
          <dd className="tabular">{formatWindSpeed(day.summary.windSpeedKph)}</dd>
        </div>
        <div className="inline-flex items-center gap-1.5">
          <Thermometer className="size-4 shrink-0" aria-hidden="true" />
          <dt className="sr-only">Temperature range</dt>
          <dd className="tabular">
            {formatTemperature(day.summary.tempMaxC)} / {formatTemperature(day.summary.tempMinC)}
          </dd>
        </div>
      </dl>
    </section>
  )
}
