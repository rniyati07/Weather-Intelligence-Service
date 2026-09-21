import {
  BedDouble,
  Dumbbell,
  Landmark,
  MapPin,
  TreePine,
  UtensilsCrossed,
  Waves,
} from 'lucide-react'
import type { ComponentType } from 'react'

import type { ChatPlace } from '@/types'
import { titleCaseSlug } from '@/utils/format'
import { cn } from '@/lib/utils'

/** Best-effort, mirroring the backend's own OSM tag mapping: a reasonable icon
 * beats none, and an unmapped category still renders with the generic pin. */
const PLACE_ICONS: Record<string, ComponentType<{ className?: string }>> = {
  beach: Waves,
  water_sports: Waves,
  adventure: Waves,
  museum: Landmark,
  cultural_site: Landmark,
  landmark: Landmark,
  viewpoint: Landmark,
  photography: Landmark,
  restaurant: UtensilsCrossed,
  food: UtensilsCrossed,
  nature: TreePine,
  outdoor_activity: TreePine,
  hiking: TreePine,
  wildlife: TreePine,
  hotel: BedDouble,
  guest_house: BedDouble,
  sports_facility: Dumbbell,
}

/** `weatherSuitability` is the engine's own verdict on the place for this
 * trip's weather — shown as a quiet cue, never recomputed here. */
const SUITABILITY_CLASSES: Record<string, string> = {
  ideal: 'text-risk-low',
  good: 'text-risk-low',
  neutral: 'text-muted-foreground',
  poor: 'text-risk-moderate',
  unsuitable: 'text-risk-high',
}

export interface PlaceListProps {
  places: ChatPlace[]
  className?: string
}

/** `reason` is a *day-level* weather note (`attraction_matching._weather_note`):
 * every place scored against the same day and suitability carries the exact
 * same sentence. Repeating it under each row is noise, so an identical note
 * shared by the whole list is lifted into one caption instead. */
function sharedReason(places: ChatPlace[]): string | null {
  const first = places[0]?.reason?.trim()
  if (!first) return null
  return places.every((place) => place.reason.trim() === first) ? first : null
}

/**
 * Real places from the backend Places provider — name, category, and the
 * deterministic `reason` the matcher recorded.
 *
 * Never rendered from prose, never invented, and never shown as an empty
 * section: an empty `places[]` renders nothing at all.
 */
export function PlaceList({ places, className }: PlaceListProps) {
  if (places.length === 0) return null

  const shared = sharedReason(places)

  return (
    <div className={cn('flex flex-col', className)}>
      {shared ? (
        <p className="border-b border-border pb-2.5 text-body-sm text-muted-foreground">{shared}</p>
      ) : null}

      <ul className="flex flex-col" aria-label="Places from the places provider">
        {places.map((place, index) => {
          const Icon = PLACE_ICONS[place.type] ?? MapPin
          return (
            <li
              key={`${place.name}-${String(index)}`}
              className="flex gap-3 border-b border-border py-3 last:border-b-0"
            >
              <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <Icon className="size-4" />
              </span>

              <div className="min-w-0 flex-1">
                <p className="truncate text-body font-medium text-heading">{place.name}</p>
                <p className="text-body-sm text-muted-foreground">{titleCaseSlug(place.type)}</p>

                {/* Only when it actually differs per place — an identical note
                  across the list is already shown once, above. */}
                {place.reason && !shared ? (
                  <p
                    className={cn(
                      'mt-0.5 text-body-sm',
                      SUITABILITY_CLASSES[place.weatherSuitability] ?? 'text-muted-foreground',
                    )}
                  >
                    {place.reason}
                  </p>
                ) : null}

                {place.address ? (
                  <p className="mt-0.5 truncate text-caption text-subtle-foreground">
                    {place.address}
                  </p>
                ) : null}
              </div>

              {/* The engine's own verdict on this place for this trip's weather,
                kept as a compact cue so the row stays scannable. */}
              <span
                className={cn(
                  'mt-0.5 shrink-0 text-caption font-medium',
                  SUITABILITY_CLASSES[place.weatherSuitability] ?? 'text-muted-foreground',
                )}
              >
                {titleCaseSlug(place.weatherSuitability)}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
