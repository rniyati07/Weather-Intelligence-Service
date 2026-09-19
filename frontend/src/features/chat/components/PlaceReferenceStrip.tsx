import { Landmark, MapPin, TreePine, UtensilsCrossed, Waves } from 'lucide-react'
import type { ComponentType } from 'react'

import { Tooltip } from '@/components/ui/tooltip'
import type { ChatPlace } from '@/types'
import { titleCaseSlug } from '@/utils/format'

/** Approximate, best-effort — the same spirit as the backend's own OSM tag
 * mapping (`attraction_matching.py`): a reasonable icon beats none, and an
 * unmapped category still renders with the generic pin. */
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
}

export interface PlaceReferenceStripProps {
  places: ChatPlace[]
}

/**
 * Real places grounding a reply — a citation, not a listing (master prompt,
 * "Place Visual Hierarchy": "Places are references, not products"). Every
 * entry came from the backend's structured `places[]`; nothing here is read
 * from the assistant's own text.
 *
 * Renders nothing when `places` is empty, rather than an empty section
 * (master prompt, "Places": "If places[] is empty → render no places area").
 */
export function PlaceReferenceStrip({ places }: PlaceReferenceStripProps) {
  if (places.length === 0) return null

  return (
    <ul className="ml-[34px] flex flex-wrap gap-2" aria-label="Places mentioned in this reply">
      {places.map((place, index) => {
        const Icon = PLACE_ICONS[place.type] ?? MapPin
        return (
          <li key={`${place.name}-${String(index)}`}>
            <Tooltip content={place.reason}>
              <span className="inline-flex max-w-[16rem] items-center gap-1.5 rounded-full border border-border bg-surface-raised px-3 py-1.5 text-body-sm text-foreground">
                <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="truncate">{place.name}</span>
                <span className="shrink-0 text-caption text-subtle-foreground">
                  {titleCaseSlug(place.type)}
                </span>
              </span>
            </Tooltip>
          </li>
        )
      })}
    </ul>
  )
}
