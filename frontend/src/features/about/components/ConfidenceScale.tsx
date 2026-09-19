import { Card } from '@/components/ui/card'
import { CONFIDENCE_BANDS } from '@/constants/domain'
import { cn } from '@/lib/utils'

/**
 * What `travelConfidence` means — FDS §5.7.
 *
 * Rendered from `CONFIDENCE_BANDS`, the same constant the dashboard's
 * confidence card reads. A page explaining the thresholds is worthless if it
 * can fall out of step with them.
 *
 * Confidence is about the *assessment*, not the weather: a low-confidence
 * "low risk" is still low risk, just less certain. That distinction is the
 * reason this section exists at all (FDS §1.3).
 */
export function ConfidenceScale() {
  return (
    <Card className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <p className="text-body text-muted-foreground">
          Every result carries a confidence value between 0 and 1, computed from three things: how
          far ahead the dates are, how well the underlying sources agree, and how complete the data
          for those days is.
        </p>
        <p className="text-body text-muted-foreground">
          It is shown in words rather than as a decimal, because a number on its own invites a
          precision the forecast does not have.
        </p>
      </div>

      <table className="w-full border-collapse text-body-sm">
        <caption className="sr-only">Confidence values and the labels they are shown as</caption>
        <thead>
          <tr className="border-b border-border text-left">
            <th scope="col" className="pb-2 text-caption font-medium text-muted-foreground">
              Value
            </th>
            <th scope="col" className="pb-2 text-caption font-medium text-muted-foreground">
              Shown as
            </th>
          </tr>
        </thead>
        <tbody>
          {CONFIDENCE_BANDS.map((band, index) => {
            const upper = index === 0 ? null : CONFIDENCE_BANDS[index - 1]?.min
            const range =
              upper === undefined || upper === null
                ? `${band.min.toFixed(2)} and above`
                : `${band.min.toFixed(2)} – ${(upper - 0.01).toFixed(2)}`

            return (
              <tr key={band.label} className="border-b border-border last:border-0">
                <td className="tabular py-3 text-muted-foreground">{range}</td>
                <td
                  className={cn('py-3 font-medium', {
                    'text-risk-low': band.tone === 'low',
                    'text-risk-moderate': band.tone === 'moderate',
                    'text-risk-high': band.tone === 'high',
                  })}
                >
                  {band.label}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}
