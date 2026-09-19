import { Check, Copy, Luggage } from 'lucide-react'
import { useCallback } from 'react'

import { EmptyState } from '@/components/feedback/EmptyState'
import { SectionContainer } from '@/components/layout/SectionContainer'
import { Button } from '@/components/ui/button'
import { STORAGE_KEYS, STORAGE_TTL_MS } from '@/constants/storage'
import { useCopyToClipboard } from '@/hooks/useCopyToClipboard'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import { cn } from '@/lib/utils'
import type { IsoDate, LocationId } from '@/types'

export interface PackingSectionProps {
  items: string[]
  locationId: LocationId
  startDate: IsoDate
  endDate: IsoDate
}

/**
 * Packing checklist — FDS §6.4.
 *
 * Converts intelligence into an action, which for two of the five personas is
 * the thing they actually came for.
 *
 * Checked state persists to `localStorage` keyed by `(location, dates)` — a
 * user ticks items off over several days before a trip, and losing that on
 * refresh would make the feature useless. It is the only optimistic-feeling
 * state in the product, and it is purely local: there is no server round-trip
 * to be optimistic about (FDS §15.6).
 *
 * An empty list is a **positive** outcome — "Nothing special needed" — not an
 * error and not a blank region.
 */
export function PackingSection({ items, locationId, startDate, endDate }: PackingSectionProps) {
  const storageKey = `${STORAGE_KEYS.packingChecklist}:${locationId}:${startDate}:${endDate}`
  const [checked, setChecked] = useLocalStorage<string[]>(
    storageKey,
    [],
    STORAGE_TTL_MS.packingChecklist,
  )
  const { copied, copy } = useCopyToClipboard()

  const toggle = useCallback(
    (item: string) => {
      setChecked((current) =>
        current.includes(item) ? current.filter((entry) => entry !== item) : [...current, item],
      )
    },
    [setChecked],
  )

  if (items.length === 0) {
    return (
      <SectionContainer id="packing" title="Packing">
        <EmptyState
          variant="positive"
          icon={Luggage}
          headline="Nothing special to pack"
          body="No weather-driven items for these dates. Travel light."
        />
      </SectionContainer>
    )
  }

  return (
    <SectionContainer
      id="packing"
      title="Packing"
      actions={
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            void copy(items.map((item) => `• ${item}`).join('\n'))
          }}
        >
          {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copied ? 'Copied' : 'Copy list'}
        </Button>
      }
    >
      <ul className="grid gap-3 md:grid-cols-2">
        {items.map((item) => {
          const isChecked = checked.includes(item)

          return (
            <li key={item}>
              <label
                className={cn(
                  'relative flex cursor-pointer items-center gap-3 rounded-lg border border-border p-4',
                  'transition-colors duration-150 ease-out hover:bg-muted/40',
                )}
              >
                {/* The input is stretched over the whole row rather than sized
                    to the 20px box: the row *is* the touch target, and a
                    20px-tall control would fail it. The visible box below is
                    presentational, since an `appearance-none` checkbox has no
                    glyph of its own. */}
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => {
                    toggle(item)
                  }}
                  className={cn(
                    'absolute inset-0 size-full cursor-pointer appearance-none rounded-lg',
                    'outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
                  )}
                />

                <span
                  aria-hidden="true"
                  className={cn(
                    'pointer-events-none flex size-5 shrink-0 items-center justify-center rounded-sm border',
                    'transition-colors duration-150',
                    isChecked ? 'border-primary bg-primary' : 'border-border-strong bg-surface',
                  )}
                >
                  <Check
                    className={cn(
                      'size-3.5 text-primary-foreground transition-opacity',
                      isChecked ? 'opacity-100' : 'opacity-0',
                    )}
                  />
                </span>

                <span
                  className={cn(
                    'pointer-events-none text-body transition-colors',
                    isChecked ? 'text-muted-foreground line-through' : 'text-foreground',
                  )}
                >
                  {item}
                </span>
              </label>
            </li>
          )
        })}
      </ul>
    </SectionContainer>
  )
}
