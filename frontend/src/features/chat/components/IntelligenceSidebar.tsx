import { Backpack, Droplets, Info, MapPin, Wind } from 'lucide-react'

import { SkeletonText } from '@/components/ui/skeleton'
import { WeatherIcon } from '@/components/weather/WeatherIcon'
import type { ChatPlace, DailyIntelligence, TripSummary } from '@/types'
import { formatCondition } from '@/utils/domain'
import { formatPercent, formatTemperature, formatWindSpeed, titleCaseSlug } from '@/utils/format'
import { PlaceList } from './PlaceList'

export interface IntelligenceSidebarProps {
  destinationName: string
  /** The day the glance card speaks for — the selected day, so the panel and
   * the conversation never disagree about which day is on screen. */
  glanceDay: DailyIntelligence | undefined
  summary: TripSummary | undefined
  /** Places from the most recent turn that returned any. */
  places: ChatPlace[]
  /** What the trip's interests were matched against, for the places caption. */
  interests: string[]
  isPending: boolean
  isError: boolean
}

/**
 * The reference's right-hand "intelligence layer" — a persistent property of
 * the active trip, not a widget belonging to one response.
 *
 * It stays mounted for as long as the trip is active: through a follow-up of
 * any intent, through a refetch after the context changes, and through a
 * failed intelligence call. Only its *contents* narrow, because a layer that
 * appears and disappears as the user asks different questions reads as a bug
 * and makes the workspace's whole shape jump.
 *
 * Secondary by construction: it restates structured data the conversation is
 * already grounded in, never anything parsed out of the assistant's prose.
 */
export function IntelligenceSidebar({
  destinationName,
  glanceDay,
  summary,
  places,
  interests,
  isPending,
  isError,
}: IntelligenceSidebarProps) {
  const packing = summary?.overallPackingList ?? []

  return (
    <div className="flex flex-col gap-7">
      <p className="text-caption font-semibold tracking-[0.14em] text-muted-foreground uppercase">
        The intelligence layer
      </p>

      {/* The layer belongs to the active trip, so it stays mounted through a
          refetch and through a failure — only its contents narrow. Removing
          it would make the workspace flicker every time the trip changes. */}
      {isPending ? (
        <div className="flex flex-col gap-3" aria-label="Loading trip intelligence">
          <SkeletonText lines={3} />
          <SkeletonText lines={4} />
        </div>
      ) : null}

      {isError ? (
        <p className="rounded-lg border border-border bg-surface p-4 text-body-sm text-muted-foreground">
          Trip intelligence is unavailable right now. The conversation still works, and this updates
          on your next message.
        </p>
      ) : null}

      {glanceDay ? (
        <section aria-label={`${destinationName} at a glance`}>
          <h2 className="text-h3 font-bold text-heading">{destinationName} at a glance</h2>

          <div className="mt-4 rounded-lg border border-border bg-surface p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <WeatherIcon
                  condition={glanceDay.summary.condition}
                  className="size-7 text-accent"
                />
                <div>
                  <p className="tabular text-metric font-bold text-heading">
                    {formatTemperature(glanceDay.summary.tempMaxC, 'celsius', { withUnit: false })}
                  </p>
                  <p className="text-body-sm text-muted-foreground">
                    {formatCondition(glanceDay.summary.condition).label}
                  </p>
                </div>
              </div>

              <dl className="flex flex-col gap-1.5 text-body-sm text-muted-foreground">
                <div className="flex items-center justify-end gap-1.5">
                  <Droplets className="size-3.5 shrink-0" aria-hidden="true" />
                  <dt className="sr-only">Chance of rain</dt>
                  <dd className="tabular">
                    {formatPercent(glanceDay.summary.precipitationProbability)} rain
                  </dd>
                </div>
                <div className="flex items-center justify-end gap-1.5">
                  <Wind className="size-3.5 shrink-0" aria-hidden="true" />
                  <dt className="sr-only">Wind speed</dt>
                  <dd className="tabular">{formatWindSpeed(glanceDay.summary.windSpeedKph)}</dd>
                </div>
              </dl>
            </div>
          </div>
        </section>
      ) : null}

      {/* Present for the whole active trip. An empty provider result is a
          state of this section, not a reason to unmount it — otherwise the
          layer's shape would change every time a turn happened to fetch no
          attractions. */}
      {!isPending && !isError ? (
        <section aria-label="Places for your trip" className="border-t border-border pt-6">
          <h2 className="flex items-center gap-2 text-h4 font-semibold text-heading">
            <MapPin className="size-4 text-muted-foreground" aria-hidden="true" />
            Places for your trip
          </h2>

          {places.length > 0 ? (
            <>
              {interests.length > 0 ? (
                <p className="mt-1 text-body-sm text-muted-foreground">
                  Matched to{' '}
                  {interests.map((interest) => titleCaseSlug(interest).toLowerCase()).join(', ')}.
                </p>
              ) : null}
              <PlaceList places={places} className="mt-3" />
            </>
          ) : (
            <p className="mt-2 text-body-sm text-muted-foreground">
              No places found near this destination yet. Ask what there is to do and I’ll look
              again.
            </p>
          )}
        </section>
      ) : null}

      {/* Same rule as places: a section of the active trip's layer, so an
          empty packing list is a positive statement rather than a missing
          block — "nothing special needed" is real information. */}
      {!isPending && !isError ? (
        <section aria-label="Packing signal" className="border-t border-border pt-6">
          <h2 className="flex items-center gap-2 text-h4 font-semibold text-heading">
            <Backpack className="size-4 text-muted-foreground" aria-hidden="true" />
            Packing signal
          </h2>

          {packing.length > 0 ? (
            <>
              <ul className="mt-3 flex flex-col gap-2">
                {packing.map((item) => (
                  <li key={item} className="flex items-center gap-2.5 text-body-sm text-foreground">
                    <span
                      className="size-1.5 shrink-0 rounded-full bg-primary"
                      aria-hidden="true"
                    />
                    {titleCaseSlug(item)}
                  </li>
                ))}
              </ul>
              <p className="mt-3 flex gap-2 text-caption text-subtle-foreground">
                <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                Drawn from every day in your range, so one wet day still puts a jacket on the list.
              </p>
            </>
          ) : (
            <p className="mt-2 text-body-sm text-muted-foreground">
              Nothing special needed for this forecast.
            </p>
          )}
        </section>
      ) : null}
    </div>
  )
}
