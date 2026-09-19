import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { DomainIcon } from '@/components/weather/DomainIcon'
import { RISK_FACTOR_TYPE_META, TRAVEL_ADVISORY_META } from '@/constants/domain'
import { TRAVEL_ADVISORIES } from '@/types'
import { formatAdvisory, formatRiskFactorType } from '@/utils/domain'

/**
 * How a verdict is computed — FDS §5.7.
 *
 * Written as an ordered chain because that is what makes the product
 * auditable: a reader can follow a number on the dashboard back to the reading
 * it came from. "The system said so" is never the answer (FDS §1.3).
 *
 * The factor types and advisory mapping are rendered from the same constants
 * the dashboard uses, so this page cannot drift out of step with the product it
 * describes.
 */

const STEPS = [
  {
    title: 'Normalized readings',
    body: 'Forecast data is fetched and converted into one internal vocabulary — temperature, precipitation probability and amount, wind speed, humidity, and a single condition per day. Nothing product-specific has happened yet.',
  },
  {
    title: 'Rules fire',
    body: 'A versioned rule set is evaluated against each day. Every rule that fires produces a risk factor carrying its own identifier, so any factor on screen can be traced back to the exact rule that produced it.',
  },
  {
    title: 'Risk becomes an advisory',
    body: 'The factors for a day are combined into that day’s risk level, which maps directly onto the advisory shown on the timeline. The mapping is fixed, not judged.',
  },
  {
    title: 'Days roll up into a trip',
    body: 'Per-day results are aggregated into the trip suitability score, the best and worst days, the packing list, and the overall risk level. Every one of those is derived from the days below it.',
  },
] as const

export function DecisionPipeline() {
  return (
    <div className="flex flex-col gap-6">
      <ol className="flex flex-col gap-4">
        {STEPS.map((step, index) => (
          <li key={step.title}>
            <Card className="flex gap-4">
              <span
                aria-hidden="true"
                className="tabular flex size-8 shrink-0 items-center justify-center rounded-full bg-primary-subtle text-body-sm font-semibold text-primary"
              >
                {index + 1}
              </span>

              <div className="flex min-w-0 flex-col gap-1.5">
                <h3 className="text-h4 font-semibold text-heading">{step.title}</h3>
                <p className="text-body text-muted-foreground">{step.body}</p>
              </div>
            </Card>
          </li>
        ))}
      </ol>

      <Card className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <h3 className="text-h4 font-semibold text-heading">The factors a rule can raise</h3>
          <p className="text-body-sm text-muted-foreground">
            These are the categories in this version. The set is designed to grow, so a factor you
            do not recognise is new rather than broken.
          </p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {Object.keys(RISK_FACTOR_TYPE_META).map((type) => {
              const meta = formatRiskFactorType(type)
              return (
                <li key={type}>
                  <Badge variant="outline" icon={<DomainIcon name={meta.icon} />}>
                    {meta.label}
                  </Badge>
                </li>
              )
            })}
          </ul>
        </div>

        <div className="flex flex-col gap-2 border-t border-border pt-5">
          <h3 className="text-h4 font-semibold text-heading">Risk maps to advice, one to one</h3>
          <p className="text-body-sm text-muted-foreground">
            A day’s advisory is not a separate judgement — it is the day’s risk level, renamed.
          </p>
          <ul className="mt-1 flex flex-wrap items-center gap-x-6 gap-y-3">
            {TRAVEL_ADVISORIES.map((advisory) => {
              const meta = formatAdvisory(advisory)
              const risk = Object.entries(TRAVEL_ADVISORY_META).find(
                ([, value]) => value.label === meta.label,
              )
              return (
                <li key={advisory} className="flex items-center gap-2 text-body-sm">
                  <span className="text-muted-foreground capitalize">{risk?.[1].tone} risk</span>
                  <span aria-hidden="true" className="text-border-strong">
                    →
                  </span>
                  <Badge tone={meta.tone} icon={<DomainIcon name={meta.icon} />}>
                    {meta.label}
                  </Badge>
                </li>
              )
            })}
          </ul>
        </div>
      </Card>
    </div>
  )
}
