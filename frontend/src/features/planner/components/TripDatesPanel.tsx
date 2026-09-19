import { CalendarDays } from 'lucide-react'
import { useId, useMemo } from 'react'

import { Chip } from '@/components/common/Chip'
import { SectionTitle } from '@/components/common/SectionTitle'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { DATE_RANGE_PRESETS } from '@/constants/dates'
import { useIsMobile } from '@/hooks/useMediaQuery'
import type { DateRange } from '@/types'
import { isCompleteRange, matchPreset, resolvePreset } from '@/utils/calendar'
import { formatDateRange } from '@/utils/date'
import { DateRangePicker } from './DateRangePicker'

export interface TripDatesPanelProps {
  value: DateRange
  onChange: (range: DateRange) => void
  onSubmit: () => void
  /** Disables the CTA until a destination is resolved, and says why. */
  submitBlockedReason: string | null
}

const PRESET_IDS = DATE_RANGE_PRESETS.map((preset) => preset.id)

/**
 * Date selection and the page's primary action — FDS §5.2.
 *
 * Presets sit above the calendar because most trips are "this weekend" or
 * "next week", and a preset is one tap where the calendar is two. `Custom` is a
 * mode rather than a range: it hands control back to the grid instead of
 * guessing dates on the user's behalf.
 *
 * The calendar shows two months at `lg` and one below (FDS §6.2). It is not
 * behind a trigger on this page: the horizon is the thing a first-time user
 * most needs to understand, and hiding the greyed-out cells behind a tap is
 * exactly how that limit gets discovered through an error instead.
 */
export function TripDatesPanel({
  value,
  onChange,
  onSubmit,
  submitBlockedReason,
}: TripDatesPanelProps) {
  const isMobile = useIsMobile()
  const headingId = useId()
  const blockedId = `${headingId}-blocked`

  const activePreset = useMemo(() => matchPreset(value, PRESET_IDS), [value])
  const complete = isCompleteRange(value)
  const canSubmit = complete && submitBlockedReason === null

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-6">
      <SectionTitle id={headingId}>Dates</SectionTitle>

      <ul className="flex flex-wrap gap-3">
        {DATE_RANGE_PRESETS.map((preset) => (
          <li key={preset.id}>
            <Chip
              selected={activePreset === preset.id}
              onClick={() => {
                const resolved = resolvePreset(preset.id)
                // `custom` resolves to null — clear the range and let the user pick.
                onChange(resolved ?? { start: null, end: null })
              }}
            >
              {preset.label}
            </Chip>
          </li>
        ))}
      </ul>

      <Card className="flex flex-col gap-6">
        <DateRangePicker value={value} onChange={onChange} months={isMobile ? 1 : 2} />

        <div className="flex flex-col gap-4 border-t border-border pt-6 md:flex-row md:items-center md:justify-between">
          <p className="flex items-center gap-2.5 text-body text-foreground">
            <CalendarDays className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            {complete ? (
              <span>{formatDateRange(value.start, value.end)}</span>
            ) : (
              <span className="text-muted-foreground">
                {value.start ? 'Choose an end date' : 'Choose your dates'}
              </span>
            )}
          </p>

          <div className="flex flex-col items-start gap-2 md:items-end">
            <Button
              variant="accent"
              size="lg"
              onClick={onSubmit}
              disabled={!canSubmit}
              aria-describedby={submitBlockedReason ? blockedId : undefined}
            >
              Get verdict
            </Button>

            {/* Never a disabled control with no explanation — the reason a CTA
                is unavailable is information the user needs. */}
            {submitBlockedReason ? (
              <p id={blockedId} className="text-body-sm text-muted-foreground">
                {submitBlockedReason}
              </p>
            ) : null}
          </div>
        </div>
      </Card>
    </section>
  )
}
