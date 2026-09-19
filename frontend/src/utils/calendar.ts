/**
 * Calendar maths — grid construction, horizon bounds, range selection.
 *
 * All pure, so the rules that decide whether a day is selectable can be reasoned
 * about (and tested) without rendering anything.
 *
 * These functions are the client-side mirror of API Spec §11. The picker uses
 * them to make an invalid range *unexpressible* rather than merely warned
 * about — a user should never see a `400 VALIDATION_ERROR` from normal
 * interaction (FDS §5.2).
 */

import { DATE_LOCALE, MAX_FORECAST_HORIZON_DAYS, MAX_TRIP_LENGTH_DAYS } from '@/constants/dates'
import type { DateRange, IsoDate } from '@/types'
import { addDays, parseIsoDate, today, toIsoDate } from './date'

/** Monday-first, matching the design. `short` repeats (T, T / S, S) — hence `full`. */
export const WEEKDAYS = [
  { short: 'M', full: 'Monday' },
  { short: 'T', full: 'Tuesday' },
  { short: 'W', full: 'Wednesday' },
  { short: 'T', full: 'Thursday' },
  { short: 'F', full: 'Friday' },
  { short: 'S', full: 'Saturday' },
  { short: 'S', full: 'Sunday' },
] as const

export interface CalendarCell {
  iso: IsoDate
  date: Date
  dayOfMonth: number
}

/** A week. `null` is a leading or trailing blank, not a day from the adjacent month. */
export type CalendarWeek = (CalendarCell | null)[]

export interface MonthView {
  year: number
  /** 0-indexed, matching `Date`. */
  monthIndex: number
  /** e.g. "August 2026". */
  title: string
  weeks: CalendarWeek[]
}

/** `Date.getDay()` is Sunday-first; the grid is Monday-first. */
function mondayFirstIndex(date: Date): number {
  return (date.getDay() + 6) % 7
}

export function formatMonthTitle(year: number, monthIndex: number): string {
  return new Intl.DateTimeFormat(DATE_LOCALE, { month: 'long', year: 'numeric' }).format(
    new Date(year, monthIndex, 1),
  )
}

/** Full accessible name for a day button, e.g. "Saturday, August 1, 2026". */
export function formatDayLabel(date: Date): string {
  return new Intl.DateTimeFormat(DATE_LOCALE, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(date)
}

/**
 * Build one month as rows of seven.
 *
 * Blanks are `null` rather than greyed-out days from the neighbouring month:
 * with a 16-day horizon those neighbours are almost always unselectable, and
 * rendering them only invites clicks that do nothing.
 */
export function buildMonthView(year: number, monthIndex: number): MonthView {
  const first = new Date(year, monthIndex, 1)
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate()
  const leading = mondayFirstIndex(first)

  const cells: CalendarWeek = Array.from({ length: leading }, () => null)

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(year, monthIndex, day)
    cells.push({ iso: toIsoDate(date), date, dayOfMonth: day })
  }

  while (cells.length % 7 !== 0) cells.push(null)

  const weeks: CalendarWeek[] = []
  for (let index = 0; index < cells.length; index += 7) {
    weeks.push(cells.slice(index, index + 7))
  }

  return { year, monthIndex, title: formatMonthTitle(year, monthIndex), weeks }
}

/** Step a year/month pair by whole months, rolling the year over. */
export function shiftMonth(
  year: number,
  monthIndex: number,
  delta: number,
): { year: number; monthIndex: number } {
  const shifted = new Date(year, monthIndex + delta, 1)
  return { year: shifted.getFullYear(), monthIndex: shifted.getMonth() }
}

export interface ForecastBounds {
  /** Earliest servable day — today. v1 forecast endpoints do not serve history. */
  min: IsoDate
  /** Latest servable day — today + the horizon. */
  max: IsoDate
}

/** The servable window, mirroring API Spec §11 "Range length". */
export function forecastBounds(now: Date = today()): ForecastBounds {
  return { min: toIsoDate(now), max: toIsoDate(addDays(now, MAX_FORECAST_HORIZON_DAYS)) }
}

/**
 * Whether a day can be clicked.
 *
 * Two rules compose. The horizon rule always applies. The span rule applies
 * only while a start is chosen and an end is not: from that point the window
 * narrows to what keeps the trip within `MAX_TRIP_LENGTH_DAYS`, in *both*
 * directions — clicking before the start is legitimate, because a reversed
 * selection swaps rather than erroring.
 */
export function isDaySelectable(
  iso: IsoDate,
  bounds: ForecastBounds,
  pendingStart: IsoDate | null,
): boolean {
  if (iso < bounds.min || iso > bounds.max) return false
  if (!pendingStart) return true

  const start = parseIsoDate(pendingStart)
  if (!start) return true

  const reach = MAX_TRIP_LENGTH_DAYS - 1
  return iso >= toIsoDate(addDays(start, -reach)) && iso <= toIsoDate(addDays(start, reach))
}

/**
 * Fold a click into the range.
 *
 * Click one begins a range; click two closes it. A complete range starts over,
 * which is what makes "pick a different week" a single click rather than a
 * clear-then-reselect.
 */
export function applyDaySelection(range: DateRange, iso: IsoDate): DateRange {
  if (!range.start || range.end) return { start: iso, end: null }

  // ISO dates compare correctly as strings, so a reversed pick simply swaps.
  return iso < range.start ? { start: iso, end: range.start } : { start: range.start, end: iso }
}

export function isCompleteRange(range: DateRange): range is { start: IsoDate; end: IsoDate } {
  return range.start !== null && range.end !== null
}

/** True when `iso` sits strictly between the two ends of a complete range. */
export function isWithinRange(iso: IsoDate, range: DateRange): boolean {
  if (!isCompleteRange(range)) return false
  return iso > range.start && iso < range.end
}

export function isRangeEndpoint(iso: IsoDate, range: DateRange): boolean {
  return iso === range.start || iso === range.end
}

/**
 * Resolve a preset to concrete dates, clamped to the horizon.
 *
 * `custom` resolves to null: it is a mode, not a range — it hands control back
 * to the calendar rather than picking dates on the user's behalf.
 */
export function resolvePreset(presetId: string, now: Date = today()): DateRange | null {
  const bounds = forecastBounds(now)

  const clamp = (start: Date, end: Date): DateRange => ({
    start: toIsoDate(start),
    end: toIsoDate(end) > bounds.max ? bounds.max : toIsoDate(end),
  })

  switch (presetId) {
    case 'weekend': {
      // Days until the coming Saturday; 0 when today already is one.
      const saturday = addDays(now, (6 - now.getDay() + 7) % 7)
      return clamp(saturday, addDays(saturday, 1))
    }
    case 'next-3-days':
      return clamp(now, addDays(now, 2))
    case 'next-week':
      return clamp(now, addDays(now, 6))
    default:
      return null
  }
}

/** Which preset the current range corresponds to, or `custom` if none. */
export function matchPreset(range: DateRange, presetIds: readonly string[], now?: Date): string {
  if (!isCompleteRange(range)) return 'custom'

  const match = presetIds.find((id) => {
    const resolved = resolvePreset(id, now)
    return resolved?.start === range.start && resolved.end === range.end
  })

  return match ?? 'custom'
}
