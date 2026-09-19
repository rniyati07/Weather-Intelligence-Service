import { MapPin } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { GeocodedPlace } from '@/types'
import { formatPlaceContext } from '@/utils/format'

export interface PlaceResultListProps {
  id: string
  places: GeocodedPlace[]
  /** Index of the option under roving focus, or -1. Drives `aria-activedescendant`. */
  activeIndex: number
  selectedId: string | null
  onSelect: (place: GeocodedPlace) => void
  optionId: (index: number) => string
}

/**
 * Geocoding results — FDS §6.2 LocationSelector.
 *
 * Every row shows region and country, not just the name. That is the entire
 * reason the list exists: "Goa" is three different places, and a name alone
 * gives the user no way to tell which one they are about to get a verdict for.
 *
 * A listbox rather than a list of buttons, so the input can own focus while
 * arrow keys move through options — the combobox pattern in `DestinationPicker`
 * depends on that split.
 */
export function PlaceResultList({
  id,
  places,
  activeIndex,
  selectedId,
  onSelect,
  optionId,
}: PlaceResultListProps) {
  return (
    <ul
      id={id}
      role="listbox"
      aria-label="Matching places"
      className="flex flex-col rounded-lg border border-border bg-surface-raised p-1.5 shadow-md"
    >
      {places.map((place, index) => {
        const context = formatPlaceContext(place)
        const isActive = index === activeIndex

        return (
          <li key={place.id}>
            <button
              type="button"
              id={optionId(index)}
              role="option"
              aria-selected={place.id === selectedId}
              // The input keeps focus, so the pointer must not steal it before
              // the click lands.
              onMouseDown={(event) => {
                event.preventDefault()
              }}
              onClick={() => {
                onSelect(place)
              }}
              className={cn(
                'flex w-full items-center gap-3 rounded-md px-3 py-3 text-left',
                'transition-colors duration-150 ease-out',
                isActive ? 'bg-muted' : 'hover:bg-muted/60',
              )}
            >
              <MapPin className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />

              <span className="flex min-w-0 flex-col">
                <span className="text-body font-medium text-heading">{place.name}</span>
                {context ? (
                  <span className="text-body-sm text-muted-foreground">{context}</span>
                ) : null}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
