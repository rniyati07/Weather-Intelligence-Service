import { ChevronDown } from 'lucide-react'
import { useId, useState } from 'react'

import { LoadingSkeleton } from '@/components/feedback/LoadingSkeleton'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Card } from '@/components/ui/card'
import { WeatherIcon } from '@/components/weather/WeatherIcon'
import { usePreferences } from '@/hooks/usePreferences'
import { cn } from '@/lib/utils'
import type { RawWeatherReading } from '@/types'
import { formatDate } from '@/utils/date'
import {
  formatPercent,
  formatPrecipitationMm,
  formatTemperature,
  formatWindSpeed,
} from '@/utils/format'

export interface RawReadingsSectionProps {
  /** Null until the section is first expanded — the fetch is lazy (FDS §7.3). */
  readings: RawWeatherReading[] | null
  loading: boolean
  onExpand: () => void
}

/**
 * Underlying normalized readings — FDS §6.5.
 *
 * Collapsed by default and fetched lazily on first expand: this is the one
 * screen region that costs an extra request, and most users never open it.
 * It exists for the sceptical user who wants to check the numbers behind the
 * judgement — which is a first-class need, not a hidden debug panel.
 *
 * `precipitationMm` and `humidity` are genuinely nullable and render as "—",
 * never as `0`. A missing measurement and a measurement of zero are different
 * facts, and conflating them would misrepresent the data.
 */
export function RawReadingsSection({ readings, loading, onExpand }: RawReadingsSectionProps) {
  const [open, setOpen] = useState(false)
  const { temperatureUnit } = usePreferences()
  const panelId = useId()

  function toggle() {
    const next = !open
    setOpen(next)
    if (next && !readings && !loading) onExpand()
  }

  return (
    <section id="readings" className="scroll-mt-24">
      <Card padded={false} className="overflow-hidden">
        <h2>
          <button
            type="button"
            onClick={toggle}
            aria-expanded={open}
            aria-controls={panelId}
            className={cn(
              'flex w-full items-center justify-between gap-4 p-5 text-left md:p-6',
              'transition-colors hover:bg-muted/40',
              'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
            )}
          >
            <span className="text-h3 font-semibold text-heading">Raw readings</span>

            <span className="flex shrink-0 items-center gap-2 text-body-sm text-muted-foreground">
              <span className="hidden md:inline">Normalized forecast values</span>
              <ChevronDown
                aria-hidden="true"
                className={cn('size-4 transition-transform duration-150', open && 'rotate-180')}
              />
            </span>
          </button>
        </h2>

        <div id={panelId} hidden={!open} className="border-t border-border p-5 md:p-6">
          {loading ? <LoadingSkeleton variant="table" count={4} label="Loading readings" /> : null}

          {!loading && readings && readings.length === 0 ? (
            <EmptyState
              headline="No readings available"
              body="Underlying data isn't available for this range."
            />
          ) : null}

          {!loading && readings && readings.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[38rem] border-collapse text-body-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <Th>Date</Th>
                    <Th>Condition</Th>
                    <Th align="right">Min</Th>
                    <Th align="right">Max</Th>
                    <Th align="right">Precip.</Th>
                    <Th align="right">Rainfall</Th>
                    <Th align="right">Wind</Th>
                    <Th align="right">Humidity</Th>
                  </tr>
                </thead>
                <tbody>
                  {readings.map((reading) => (
                    <tr key={reading.date} className="border-b border-border last:border-0">
                      <Td>{formatDate(reading.date, 'weekdayShort')}</Td>
                      <Td>
                        <WeatherIcon condition={reading.condition} withLabel />
                      </Td>
                      <Td align="right">{formatTemperature(reading.tempMinC, temperatureUnit)}</Td>
                      <Td align="right">{formatTemperature(reading.tempMaxC, temperatureUnit)}</Td>
                      <Td align="right">{formatPercent(reading.precipitationProbability)}</Td>
                      <Td align="right">{formatPrecipitationMm(reading.precipitationMm)}</Td>
                      <Td align="right">{formatWindSpeed(reading.windSpeedKph)}</Td>
                      <Td align="right">{formatPercent(reading.humidity)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </Card>
    </section>
  )
}

function Th({ children, align = 'left' }: { children: React.ReactNode; align?: 'left' | 'right' }) {
  return (
    <th
      scope="col"
      className={cn('px-3 py-2 text-caption font-medium text-muted-foreground', {
        'text-right': align === 'right',
      })}
    >
      {children}
    </th>
  )
}

function Td({ children, align = 'left' }: { children: React.ReactNode; align?: 'left' | 'right' }) {
  return (
    <td
      className={cn('px-3 py-3 text-foreground', {
        'tabular text-right': align === 'right',
      })}
    >
      {children}
    </td>
  )
}
