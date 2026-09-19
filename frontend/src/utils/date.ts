/**
 * Date formatting and arithmetic.
 *
 * All pure, all `Intl`-based — no date library. The app only ever handles
 * calendar dates (`YYYY-MM-DD`) and one UTC timestamp, which `Intl` covers
 * without shipping a parser.
 *
 * Calendar dates are treated as *local* dates deliberately. `new Date('2026-08-01')`
 * parses as UTC midnight, which renders as 31 July for anyone west of Greenwich
 * — an off-by-one on the single most important value on the screen. `parseIsoDate`
 * therefore constructs the date from its parts.
 */

import { DATE_FORMATS, DATE_LOCALE } from '@/constants/dates'
import type { IsoDate, IsoDateTime } from '@/types'

const MS_PER_DAY = 86_400_000

/** Parse `YYYY-MM-DD` into a local-midnight Date. Returns null if unparseable. */
export function parseIsoDate(value: IsoDate): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return null

  const [, year, month, day] = match
  const date = new Date(Number(year), Number(month) - 1, Number(day))

  // Rejects impossible calendar dates that the regex accepts, e.g. 2026-02-31.
  return Number.isNaN(date.getTime()) ? null : date
}

/** Serialise a Date to `YYYY-MM-DD` using its local components. */
export function toIsoDate(date: Date): IsoDate {
  const year = date.getFullYear().toString().padStart(4, '0')
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Today, at local midnight. */
export function today(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

export function addDays(date: Date, days: number): Date {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

/** Whole days from `from` to `to`. Negative when `to` precedes `from`. */
export function daysBetween(from: Date, to: Date): number {
  const a = new Date(from.getFullYear(), from.getMonth(), from.getDate()).getTime()
  const b = new Date(to.getFullYear(), to.getMonth(), to.getDate()).getTime()
  return Math.round((b - a) / MS_PER_DAY)
}

/** Inclusive day count, i.e. a single-day trip is 1. */
export function inclusiveDayCount(start: Date, end: Date): number {
  return daysBetween(start, end) + 1
}

export function isSameDay(a: Date, b: Date): boolean {
  return daysBetween(a, b) === 0
}

/**
 * Format a calendar date. Unparseable input returns the raw string rather than
 * "Invalid Date" — a malformed value from the API should look like data, not
 * like a broken component.
 */
export function formatDate(
  value: IsoDate | Date,
  format: keyof typeof DATE_FORMATS = 'medium',
): string {
  const date = value instanceof Date ? value : parseIsoDate(value)
  if (!date) return String(value)
  return new Intl.DateTimeFormat(DATE_LOCALE, DATE_FORMATS[format]).format(date)
}

/**
 * Format an inclusive range, collapsing what the two ends share:
 *   "Aug 1 – 3, 2026" · "Aug 28 – Sep 2, 2026" · "Aug 1, 2026"
 */
export function formatDateRange(start: IsoDate | Date, end: IsoDate | Date): string {
  const startDate = start instanceof Date ? start : parseIsoDate(start)
  const endDate = end instanceof Date ? end : parseIsoDate(end)
  if (!startDate || !endDate) return `${String(start)} – ${String(end)}`

  const year = endDate.getFullYear()

  if (isSameDay(startDate, endDate)) return formatDate(startDate, 'medium')

  // Within one month the end needs only its day number: "Aug 1 – 3, 2026".
  const sameMonth = startDate.getFullYear() === year && startDate.getMonth() === endDate.getMonth()
  const endLabel = sameMonth ? String(endDate.getDate()) : formatDate(endDate, 'compact')

  return `${formatDate(startDate, 'compact')} – ${endLabel}, ${year}`
}

/**
 * "2m ago", "3h ago", "yesterday" — for `metadata.generatedAt`.
 * Pair with the absolute value in a title attribute (FDS §8.1).
 */
export function formatRelativeTime(value: IsoDateTime | Date, now: Date = new Date()): string {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)

  const deltaSeconds = Math.round((date.getTime() - now.getTime()) / 1000)
  const absolute = Math.abs(deltaSeconds)
  const formatter = new Intl.RelativeTimeFormat(DATE_LOCALE, { numeric: 'auto' })

  if (absolute < 45) return 'just now'
  if (absolute < 3600) return formatter.format(Math.round(deltaSeconds / 60), 'minute')
  if (absolute < 86_400) return formatter.format(Math.round(deltaSeconds / 3600), 'hour')
  return formatter.format(Math.round(deltaSeconds / 86_400), 'day')
}

/** The absolute rendering shown on hover behind a relative timestamp. */
export function formatAbsoluteTime(value: IsoDateTime | Date): string {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat(DATE_LOCALE, DATE_FORMATS.absolute).format(date)
}
