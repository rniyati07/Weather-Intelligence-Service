/**
 * A `ChatPlace` -> Google Maps URL. Purely a transformation of data the
 * backend already returned (coordinates, name, address) — never a guessed or
 * invented link, and never a fabricated website: the Places provider carries
 * no website field, so this is the one destination every place can honestly
 * offer (master prompt, "Places are references, not products" — a reference
 * a user can actually follow).
 */

import type { ChatPlace } from '@/types'

/**
 * Coordinates, when the provider supplied them, open the exact pin. Without
 * them, a text search by name (plus address, when known) still gets a user
 * to the right result far more often than no link at all.
 */
export function getPlaceMapsUrl(place: ChatPlace): string {
  if (place.latitude != null && place.longitude != null) {
    return `https://www.google.com/maps/search/?api=1&query=${String(place.latitude)},${String(place.longitude)}`
  }

  const query = [place.name, place.address].filter(Boolean).join(', ')
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`
}
