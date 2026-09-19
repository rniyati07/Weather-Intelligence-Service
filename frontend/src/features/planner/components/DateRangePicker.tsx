import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useMemo, useRef, useState, type KeyboardEvent } from 'react'

import { Separator } from '@/components/ui/separator'
import { MAX_FORECAST_HORIZON_DAYS } from '@/constants/dates'
import { cn } from '@/lib/utils'
import type { DateRange, IsoDate } from '@/types'
import {
  applyDaySelection,
  buildMonthView,
  forecastBounds,
  formatDayLabel,
  isDaySelectable,
  isRangeEndpoint,
  isWithinRange,
  shiftMonth,
  WEEKDAYS,
  type CalendarCell,
} from '@/utils/calendar'
import { addDays, parseIsoDate, today, toIsoDate } from '@/utils/date'

export interface DateRangePickerProps {
  value: DateRange
  onChange: (range: DateRange) => void
  /** Months shown side by side. Two at `lg`, one below — the caller decides. */
  months?: 1 | 2
  className?: string
}

/**
 * Date range picker — FDS §6.2.
 *
 * The governing idea: **an invalid range must be unexpressible, not merely
 * warned about.** Days outside the 16-day horizon are disabled and visibly
 * greyed, so the limit is understood rather than discovered through an error.
 * A reversed selection swaps instead of failing. Together these mean a user
 * cannot produce a request the backend would reject (API Spec §11 / FDS §5.2).
 *
 * Shared rather than feature-local because the dashboard's "Edit dates" control
 * opens the same picker — which is why layout stays the caller's decision and
 * this component only renders the calendar.
 *
 * Keyboard model is a roving-tabindex grid (FDS §14.2): arrows move by a day or
 * a week, Home/End jump within the week, PageUp/PageDown move by month. Exactly
 * one day is tabbable at a time, so the calendar costs one Tab stop rather than
 * forty.
 */
export function DateRangePicker({ value, onChange, months = 2, className }: DateRangePickerProps) {
  const now = useMemo(() => today(), [])
  const bounds = useMemo(() => forecastBounds(now), [now])

  const [viewStart, setViewStart] = useState(() => ({
    year: now.getFullYear(),
    monthIndex: now.getMonth(),
  }))

  // The roving focus target. Starts on the selected day, or today.
  const [focusedIso, setFocusedIso] = useState<IsoDate>(value.start ?? bounds.min)
  const gridRef = useRef<HTMLDivElement>(null)

  const visibleMonths = useMemo(
    () =>
      Array.from({ length: months }, (_, offset) => {
        const { year, monthIndex } = shiftMonth(viewStart.year, viewStart.monthIndex, offset)
        return buildMonthView(year, monthIndex)
      }),
    [viewStart, months],
  )

  // A start without an end means selection is in progress, which narrows what
  // is still reachable.
  const pendingStart = value.start && !value.end ? value.start : null

  const firstVisible = `${String(viewStart.year)}-${String(viewStart.monthIndex + 1).padStart(2, '0')}`
  const lastMonth = visibleMonths[visibleMonths.length - 1]
  const lastVisible = lastMonth
    ? `${String(lastMonth.year)}-${String(lastMonth.monthIndex + 1).padStart(2, '0')}`
    : firstVisible

  const canPageBack = firstVisible > bounds.min.slice(0, 7)
  const canPageForward = lastVisible < bounds.max.slice(0, 7)
  const showPaging = canPageBack || canPageForward

  function page(delta: number) {
    setViewStart((current) => shiftMonth(current.year, current.monthIndex, delta))
  }

  /** Move roving focus, scrolling the view to follow it. */
  function moveFocus(iso: IsoDate) {
    setFocusedIso(iso)

    const target = parseIsoDate(iso)
    if (!target) return

    const month = `${String(target.getFullYear())}-${String(target.getMonth() + 1).padStart(2, '0')}`
    if (month < firstVisible)
      setViewStart({ year: target.getFullYear(), monthIndex: target.getMonth() })
    if (month > lastVisible) {
      const { year, monthIndex } = shiftMonth(
        target.getFullYear(),
        target.getMonth(),
        -(months - 1),
      )
      setViewStart({ year, monthIndex })
    }

    // The button may have only just been rendered, so defer the focus call.
    requestAnimationFrame(() => {
      gridRef.current?.querySelector<HTMLButtonElement>(`[data-day="${iso}"]`)?.focus()
    })
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = parseIsoDate(focusedIso)
    if (!current) return

    const step = (days: number) => {
      event.preventDefault()
      moveFocus(toIsoDate(addDays(current, days)))
    }

    switch (event.key) {
      case 'ArrowLeft':
        return step(-1)
      case 'ArrowRight':
        return step(1)
      case 'ArrowUp':
        return step(-7)
      case 'ArrowDown':
        return step(7)
      case 'Home':
        // Back to Monday of the focused week.
        return step(-((current.getDay() + 6) % 7))
      case 'End':
        return step(6 - ((current.getDay() + 6) % 7))
      case 'PageUp': {
        event.preventDefault()
        const previous = shiftMonth(current.getFullYear(), current.getMonth(), -1)
        return moveFocus(toIsoDate(new Date(previous.year, previous.monthIndex, current.getDate())))
      }
      case 'PageDown': {
        event.preventDefault()
        const next = shiftMonth(current.getFullYear(), current.getMonth(), 1)
        return moveFocus(toIsoDate(new Date(next.year, next.monthIndex, current.getDate())))
      }
      default:
        return
    }
  }

  function selectDay(cell: CalendarCell) {
    onChange(applyDaySelection(value, cell.iso))
    setFocusedIso(cell.iso)
  }

  return (
    <div className={cn('flex flex-col gap-6', className)}>
      <div className="flex items-start gap-2">
        {/* Paging only exists for the one-month layout, where the horizon can
            straddle a month boundary. With both months on screen there is
            nowhere to page to, so the controls are omitted rather than shown
            permanently disabled. */}
        {showPaging ? (
          <PageButton
            direction="previous"
            disabled={!canPageBack}
            onClick={() => {
              page(-1)
            }}
          />
        ) : null}

        {/* No `role="application"` and no `role="grid"`: a plain table with a
            caption and column headers is what screen readers navigate best
            here, and it keeps the day buttons unambiguous toggle buttons.
            Key handling works regardless — events bubble up from the buttons. */}
        <div ref={gridRef} onKeyDown={handleKeyDown} className="grid flex-1 gap-8 lg:grid-cols-2">
          {visibleMonths.map((month) => (
            <table key={month.title} className="w-full border-collapse">
              <caption className="mb-4 text-left text-h3 font-semibold text-heading">
                {month.title}
              </caption>

              <thead>
                <tr>
                  {WEEKDAYS.map((weekday, index) => (
                    <th
                      key={`${weekday.full}-${String(index)}`}
                      scope="col"
                      abbr={weekday.full}
                      className="pb-2 text-caption font-medium text-subtle-foreground"
                    >
                      <span aria-hidden="true">{weekday.short}</span>
                      <span className="sr-only">{weekday.full}</span>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {month.weeks.map((week, weekIndex) => (
                  <tr key={`${month.title}-${String(weekIndex)}`}>
                    {week.map((cell, dayIndex) =>
                      cell === null ? (
                        <td key={`blank-${String(weekIndex)}-${String(dayIndex)}`} />
                      ) : (
                        <DayCell
                          key={cell.iso}
                          cell={cell}
                          range={value}
                          selectable={isDaySelectable(cell.iso, bounds, pendingStart)}
                          tabbable={cell.iso === focusedIso}
                          onSelect={selectDay}
                        />
                      ),
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          ))}
        </div>

        {showPaging ? (
          <PageButton
            direction="next"
            disabled={!canPageForward}
            onClick={() => {
              page(1)
            }}
          />
        ) : null}
      </div>

      <Separator label={`Forecast horizon · ${String(MAX_FORECAST_HORIZON_DAYS)} days`} />

      <p className="max-w-[68ch] text-body-sm text-muted-foreground">
        Dates beyond today + {MAX_FORECAST_HORIZON_DAYS} days are unavailable — we can&rsquo;t
        compute a reliable verdict further out. Reversed selections swap automatically.
      </p>
    </div>
  )
}

function PageButton({
  direction,
  disabled,
  onClick,
}: {
  direction: 'previous' | 'next'
  disabled: boolean
  onClick: () => void
}) {
  const Icon = direction === 'previous' ? ChevronLeft : ChevronRight

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'mt-0.5 inline-flex size-11 shrink-0 items-center justify-center rounded-md',
        'text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
        'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
        'disabled:pointer-events-none disabled:opacity-30',
      )}
    >
      <Icon className="size-4" aria-hidden="true" />
      <span className="sr-only">{direction === 'previous' ? 'Previous month' : 'Next month'}</span>
    </button>
  )
}

function DayCell({
  cell,
  range,
  selectable,
  tabbable,
  onSelect,
}: {
  cell: CalendarCell
  range: DateRange
  selectable: boolean
  tabbable: boolean
  onSelect: (cell: CalendarCell) => void
}) {
  const endpoint = isRangeEndpoint(cell.iso, range)
  const inside = isWithinRange(cell.iso, range)

  return (
    <td className="p-0.5">
      <button
        type="button"
        data-day={cell.iso}
        // Roving tabindex: one tab stop for the whole calendar, arrows for the rest.
        tabIndex={tabbable ? 0 : -1}
        disabled={!selectable}
        aria-label={formatDayLabel(cell.date)}
        aria-pressed={endpoint || inside}
        onClick={() => {
          onSelect(cell)
        }}
        className={cn(
          // Fills the column rather than sitting as a fixed square: clears the
          // 44px touch target at every width, and the wider selected pill is
          // what the design shows.
          'tabular relative flex h-11 w-full items-center justify-center rounded-md text-body',
          'transition-colors duration-150 ease-out',
          'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
          // Disabled days stay legible but obviously inert — the horizon should
          // read as a boundary, not as missing content.
          !selectable && 'cursor-not-allowed text-subtle-foreground/50',
          selectable && !endpoint && !inside && 'text-foreground hover:bg-muted',
          inside && 'bg-primary-subtle text-primary',
          endpoint && 'bg-primary font-semibold text-primary-foreground',
        )}
      >
        {cell.dayOfMonth}
      </button>
    </td>
  )
}
