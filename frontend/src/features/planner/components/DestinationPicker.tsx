import { Check, MapPin } from 'lucide-react'
import { useEffect, useId, useMemo, useState, type KeyboardEvent } from 'react'

import { SearchInput } from '@/components/common/SearchInput'
import { EmptyState } from '@/components/feedback/EmptyState'
import { SectionTitle } from '@/components/common/SectionTitle'
import { SEARCH_MIN_CHARS } from '@/constants/api'
import { useGeocoding } from '@/hooks/queries'
import type { GeocodedPlace } from '@/types'
import { formatPlaceContext } from '@/utils/format'
import { PlaceResultList } from './PlaceResultList'

export interface DestinationPickerProps {
  /** Seeds the field from `?q=` when arriving from the landing page. */
  initialQuery?: string
  selected: GeocodedPlace | null
  onSelect: (place: GeocodedPlace | null) => void
}

/**
 * Destination resolution — FDS §5.2.
 *
 * Geocoding is the client's job (API Spec §5), so this is where a place name
 * becomes coordinates. Three outcomes, all designed rather than defaulted:
 * nothing found gets an empty state that suggests adding a country; exactly one
 * match auto-selects; several matches get the disambiguation list.
 *
 * Implemented as a combobox: the input keeps focus and `aria-activedescendant`
 * points at the highlighted option, so arrow keys browse results without the
 * user losing their place in the field they are still typing in.
 */
export function DestinationPicker({
  initialQuery = '',
  selected,
  onSelect,
}: DestinationPickerProps) {
  const [query, setQuery] = useState(initialQuery)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [dismissed, setDismissed] = useState(false)

  const listboxId = useId()
  const optionId = (index: number) => `${listboxId}-option-${String(index)}`

  // Debouncing, the minimum query length and the settling flag all live in the
  // hook, so this component never knows where places come from.
  const { data, isPending, isTyping } = useGeocoding(query)
  const results = useMemo(() => data ?? [], [data])
  const isSettling = isTyping || isPending

  // Exactly one match needs no disambiguation, so it selects itself (FDS §3.1).
  useEffect(() => {
    const only = results.length === 1 ? results[0] : undefined
    if (only && !selected) onSelect(only)
  }, [results, selected, onSelect])

  const showResults = !dismissed && results.length > 0 && (results.length > 1 || !selected)
  const showEmpty = query.trim().length >= SEARCH_MIN_CHARS && !isSettling && results.length === 0

  function handleSelect(place: GeocodedPlace) {
    onSelect(place)
    setQuery(place.name)
    setDismissed(true)
    setActiveIndex(-1)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setDismissed(true)
      setActiveIndex(-1)
      return
    }

    if (!showResults) return

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        setActiveIndex((index) => (index + 1) % results.length)
        break
      case 'ArrowUp':
        event.preventDefault()
        setActiveIndex((index) => (index <= 0 ? results.length - 1 : index - 1))
        break
      case 'Enter': {
        const place = results[activeIndex]
        if (place) {
          event.preventDefault()
          handleSelect(place)
        }
        break
      }
      default:
        break
    }
  }

  return (
    <section aria-labelledby={`${listboxId}-heading`} className="flex flex-col gap-6">
      <SectionTitle id={`${listboxId}-heading`}>Destination</SectionTitle>

      <div className="flex flex-col gap-3">
        <SearchInput
          label="Search for a place"
          hideLabel={false}
          placeholder="Goa"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setDismissed(false)
            setActiveIndex(-1)
            if (selected) onSelect(null)
          }}
          onClear={() => {
            setQuery('')
            onSelect(null)
            setActiveIndex(-1)
          }}
          onKeyDown={handleKeyDown}
          loading={isSettling}
          role="combobox"
          aria-expanded={showResults}
          aria-controls={showResults ? listboxId : undefined}
          aria-activedescendant={activeIndex >= 0 ? optionId(activeIndex) : undefined}
          aria-autocomplete="list"
        />

        {showResults ? (
          <PlaceResultList
            id={listboxId}
            places={results}
            activeIndex={activeIndex}
            selectedId={selected?.id ?? null}
            onSelect={handleSelect}
            optionId={optionId}
          />
        ) : null}

        {showEmpty ? (
          <EmptyState
            icon={MapPin}
            headline="We couldn't find that place"
            body="Check the spelling, or try adding a country — 'Goa, India'."
            action={{
              label: 'Clear and retry',
              onClick: () => {
                setQuery('')
                onSelect(null)
              },
            }}
          />
        ) : null}

        {selected && !showResults ? (
          <p className="flex items-center gap-2 text-body-sm text-risk-low">
            <Check className="size-4 shrink-0" aria-hidden="true" />
            <span>
              {selected.name}
              {formatPlaceContext(selected) ? ` · ${formatPlaceContext(selected)}` : ''} selected
            </span>
          </p>
        ) : (
          <p className="text-body-sm text-muted-foreground">
            Same-named places are shown with region and country so you can tell them apart.
          </p>
        )}
      </div>
    </section>
  )
}
