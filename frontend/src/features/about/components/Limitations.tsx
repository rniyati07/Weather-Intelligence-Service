import { Card } from '@/components/ui/card'
import { MAX_FORECAST_HORIZON_DAYS, MAX_TRIP_LENGTH_DAYS } from '@/constants/dates'
import { ACTIVITY_CATEGORIES } from '@/types'

/**
 * What this product cannot do — FDS §5.7.
 *
 * Stated plainly and without hedging. A decision-support tool that is vague
 * about its limits invites more trust than it has earned, and every item here
 * is a real constraint of the current implementation rather than a disclaimer.
 */

const LIMITATIONS = [
  {
    title: `Nothing beyond ${String(MAX_FORECAST_HORIZON_DAYS)} days`,
    body: `Forecasts are served up to ${String(MAX_FORECAST_HORIZON_DAYS)} days ahead, and a single trip can span at most ${String(MAX_TRIP_LENGTH_DAYS)} days. The date picker will not let you ask for more, so you should never hit this as an error.`,
  },
  {
    title: 'No past dates',
    body: 'These are forecast endpoints. A date range that has already finished is rejected rather than answered — there is no historical mode.',
  },
  {
    title: 'Forecasts are probabilities, not promises',
    body: 'A 90% chance of rain is a 90% chance of rain. Risk levels and scores inherit that uncertainty, which is exactly what the confidence value is there to tell you.',
  },
  {
    title: 'Accuracy falls off with distance',
    body: 'A verdict for tomorrow rests on far better data than one for two weeks out. The confidence value drops accordingly; it is worth reading before acting on a distant date.',
  },
  {
    title: `Activity scoring covers ${String(ACTIVITY_CATEGORIES.length)} categories`,
    body: `This version scores ${ACTIVITY_CATEGORIES.length} activity types. If your trip depends on something else — diving, cycling, photography — the scores are a rough proxy at best.`,
  },
  {
    title: 'One language, metric units',
    body: 'Explanations are generated in English only. Measurements are metric; Fahrenheit is converted in your browser for display and changes nothing about the underlying assessment.',
  },
  {
    title: 'It does not know your trip',
    body: 'Weather is the only input. Cost, crowds, closures, local events, visas and your own tolerance for a wet afternoon are all outside what this can see.',
  },
] as const

export function Limitations() {
  return (
    <Card className="flex flex-col divide-y divide-border">
      {LIMITATIONS.map((limitation) => (
        <div key={limitation.title} className="flex flex-col gap-1.5 py-4 first:pt-0 last:pb-0">
          <h3 className="text-h4 font-semibold text-heading">{limitation.title}</h3>
          <p className="text-body text-muted-foreground">{limitation.body}</p>
        </div>
      ))}
    </Card>
  )
}
