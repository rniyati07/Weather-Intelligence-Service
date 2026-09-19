import { CloudRain, Sun } from 'lucide-react'

import type { ActivitySuitability, DailyIntelligence, TripSummary } from '@/types'
import { formatDate } from '@/utils/date'
import { formatActivity, formatAdvisory, formatRisk, TONE_CLASSES } from '@/utils/domain'
import { formatConfidence } from '@/utils/format'
import { cn } from '@/lib/utils'

export interface TripOutlookPanelProps {
  summary: TripSummary
  /** Only used to say how many days the outlook is based on. */
  dayCount: number
  bestDay: DailyIntelligence | undefined
  worstDay: DailyIntelligence | undefined
}

/**
 * The trip's headline verdict — the reference's "overall trip outlook" block.
 *
 * Score, risk level, confidence and the best/worst dates are all
 * `tripSummary` fields; the supporting line under each day comes from that
 * day's own worst risk factor, authored by the rule engine. Nothing here
 * ranks or scores anything itself.
 */
export function TripOutlookPanel({ summary, dayCount, bestDay, worstDay }: TripOutlookPanelProps) {
  const risk = formatRisk(summary.overallRiskLevel)
  const confidence = formatConfidence(summary.travelConfidence)
  const bestDate = summary.bestDays[0]
  const worstDate = summary.worstDays[0]
  // A single-day trip is its own best and worst day; showing both would be a
  // contradiction, so the watch-out half is dropped.
  const sameDay = Boolean(bestDate && worstDate && bestDate === worstDate)

  return (
    <section className="flex flex-col gap-3" aria-label="Overall trip outlook">
      <div className="rounded-lg border border-border bg-surface p-5">
        <p className="flex items-center gap-2 text-caption font-semibold tracking-[0.12em] text-muted-foreground uppercase">
          <span
            className={cn('size-1.5 rounded-full', TONE_CLASSES[risk.tone].dot)}
            aria-hidden="true"
          />
          Overall trip outlook
        </p>

        <div className="mt-4 flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
          <div className="min-w-0">
            <p className="flex items-baseline gap-2">
              <span className="tabular text-metric-lg font-bold text-heading">
                {summary.tripSuitabilityScore}
              </span>
              <span className="text-body-sm text-subtle-foreground">/ 100</span>
              <span className={cn('text-body font-medium', TONE_CLASSES[risk.tone].text)}>
                {risk.label}
              </span>
            </p>
          </div>

          <div className="w-full max-w-[13rem] shrink-0">
            <p className="text-caption text-muted-foreground">Travel confidence</p>
            <p className="mt-0.5 text-h4 font-semibold text-heading">{confidence.label}</p>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted" role="presentation">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${String((confidence.value ?? 0) * 100)}%` }}
              />
            </div>
            <p className="mt-1.5 text-caption text-subtle-foreground">
              Based on {dayCount}-day forecast
            </p>
          </div>
        </div>
      </div>

      {bestDate || worstDate ? (
        <div className="grid gap-3 md:grid-cols-2">
          {bestDate ? (
            <DayVerdict
              label={sameDay ? 'Your travel day' : 'Best day'}
              tone="low"
              icon={<Sun className="size-4" aria-hidden="true" />}
              date={bestDate}
              detail={bestDetail(bestDay)}
            />
          ) : null}

          {worstDate && !sameDay ? (
            <DayVerdict
              label="Watch-out"
              tone="high"
              icon={<CloudRain className="size-4" aria-hidden="true" />}
              date={worstDate}
              detail={worstDetail(worstDay)}
            />
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function DayVerdict({
  label,
  tone,
  icon,
  date,
  detail,
}: {
  label: string
  tone: 'low' | 'high'
  icon: React.ReactNode
  date: string
  detail: string | null
}) {
  return (
    <div className="flex gap-3 rounded-lg border border-border bg-surface p-4">
      <span
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-md',
          TONE_CLASSES[tone].surface,
          TONE_CLASSES[tone].text,
        )}
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-caption font-semibold tracking-[0.1em] text-muted-foreground uppercase">
          {label}
        </p>
        <p className="mt-0.5 truncate text-body font-semibold text-heading">
          {formatDate(date, 'medium')}
        </p>
        {detail ? <p className="mt-1 text-body-sm text-muted-foreground">{detail}</p> : null}
      </div>
    </div>
  )
}

/**
 * Why this day is the best one: what it is actually good *for*.
 *
 * The engine ranks days by risk and then by mean activity score, so the
 * honest supporting line for the winner is its own strongest activity — not
 * a risk factor, which a genuinely good day may not have at all. That is
 * also what stops both cards reading identically on a low-risk trip, where
 * the best and worst day can share a mean score.
 */
function bestDetail(day: DailyIntelligence | undefined): string | null {
  if (!day) return null

  const top = day.activitySuitability.reduce<ActivitySuitability | null>(
    (best, candidate) => (best === null || candidate.score > best.score ? candidate : best),
    null,
  )
  if (top === null) return null

  return `Best for ${formatActivity(top.activity).toLowerCase()} (${String(top.score)}/100)`
}

/**
 * Why this day needs watching: the most severe thing the rule engine
 * recorded, verbatim.
 *
 * A worst day nearly always has a triggered factor — that is what made it
 * the worst — so this reads as a reason rather than a score. When it has
 * none (a uniformly calm trip), the advisory carries the meaning instead.
 */
function worstDetail(day: DailyIntelligence | undefined): string | null {
  if (!day) return null

  const factors = day.riskAssessment.riskFactors
  if (factors.length > 0) {
    const high = factors.find((factor) => factor.severity === 'high')
    return (high ?? factors[0])?.description ?? null
  }

  const advisory = formatAdvisory(day.travelAdvisory)
  return `${advisory.label} — the least settled day of the trip`
}
