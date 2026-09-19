import { CalendarDays, CloudSun, MapPin, Settings } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useParams, useSearchParams } from 'react-router'

import { UnitsToggle } from '@/components/common/UnitsToggle'
import { APP_NAME, APP_WORDMARK } from '@/constants/app'
import { NAV_LINKS, QUERY_PARAMS, ROUTES } from '@/constants/routes'
import { useResolvedPlace } from '@/hooks/queries'
import { cn } from '@/lib/utils'
import { formatDateRange } from '@/utils/date'
import { formatPlaceContext } from '@/utils/format'

/**
 * Navigation bar — FDS §6.1.
 *
 * Sticky, with the bottom border appearing only after 8px of scroll so the
 * header reads as flush with the hero on arrival and as a distinct bar once the
 * user is into the content.
 *
 * On the results route it swaps its links for trip context — destination, date
 * range, units — because that is the state a user needs to keep in view while
 * scrolling a long page, and the primary nav is redundant once they are inside
 * a result.
 */
export function Navbar() {
  const scrolled = useScrolled(8)
  const trip = useTripContext()

  return (
    <header
      className={cn(
        'sticky top-0 z-40 bg-background/85 backdrop-blur-md',
        'transition-[border-color,box-shadow] duration-150 ease-out',
        scrolled ? 'border-b border-border' : 'border-b border-transparent',
      )}
    >
      <nav
        aria-label="Main"
        className="mx-auto flex h-16 w-full max-w-[80rem] items-center gap-3 px-4 md:gap-6 md:px-6 lg:px-8"
      >
        <Link
          to={ROUTES.home}
          // `min-h-11` grows the hit area to the 44px touch target without
          // changing how the wordmark looks inside the 64px bar (FDS §10.4).
          className="flex min-h-11 shrink-0 items-center gap-2.5 rounded-md focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <CloudSun className="size-6 text-primary" aria-hidden="true" />
          {/* On a phone inside a trip, the wordmark plus the units toggle plus
              settings exceed 390px and push the gear off-screen. The icon and
              the screen-reader name carry the link on their own. */}
          <span className={cn('text-h4 font-bold', trip && 'hidden md:inline')}>
            <span className="text-heading">{APP_WORDMARK.primary}</span>
            <span className="text-primary">{APP_WORDMARK.secondary}</span>
          </span>
          <span className="sr-only">{APP_NAME} — home</span>
        </Link>

        <div className="flex-1" />

        {trip ? (
          <>
            <p className="hidden items-center gap-2 rounded-full border border-border px-3 py-1.5 text-body-sm text-foreground md:inline-flex">
              <MapPin className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              {trip.name}
            </p>

            <p className="hidden items-center gap-2 text-body-sm text-muted-foreground lg:inline-flex">
              <CalendarDays className="size-4 shrink-0" aria-hidden="true" />
              {trip.dateRange}
            </p>

            <UnitsToggle />
          </>
        ) : (
          /* NavLink sets aria-current="page" on the active route itself (FDS §14.4). */
          <ul className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  className={({ isActive }) =>
                    cn(
                      'inline-flex min-h-11 items-center rounded-md px-3 text-body transition-colors hover:bg-muted',
                      'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
                      isActive ? 'font-medium text-heading' : 'text-muted-foreground',
                    )
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        )}

        <NavLink
          to={ROUTES.settings}
          className={({ isActive }) =>
            cn(
              'inline-flex size-11 items-center justify-center rounded-md transition-colors hover:bg-muted',
              'focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none',
              isActive ? 'text-heading' : 'text-muted-foreground',
            )
          }
        >
          <Settings className="size-5" aria-hidden="true" />
          <span className="sr-only">Settings</span>
        </NavLink>
      </nav>
    </header>
  )
}

/**
 * Trip context from the URL, or null when not on a result.
 *
 * Reads the same query parameters the dashboard does rather than taking props,
 * so the shell needs no coupling to the feature — the URL is the shared source
 * of truth (FDS §15.2).
 */
function useTripContext(): { name: string; dateRange: string } | null {
  const { pathname } = useLocation()
  const params = useParams<{ locationId?: string }>()
  const [searchParams] = useSearchParams()

  const isResults = pathname === ROUTES.results || pathname.startsWith('/trip/')
  const locationId = params.locationId ?? searchParams.get(QUERY_PARAMS.locationId)
  const start = searchParams.get(QUERY_PARAMS.startDate)
  const end = searchParams.get(QUERY_PARAMS.endDate)

  // Called unconditionally — hooks may not sit behind an early return.
  const place = useResolvedPlace(isResults ? locationId : null)

  if (!isResults || !locationId || !start || !end) return null

  const context = place ? formatPlaceContext(place) : ''

  return {
    // Falls back to the raw coordinate pair when the geocoder has no name for
    // it, matching how the header itself degrades (FDS §8.8).
    name: place ? [place.name, context.split(', ').pop()].filter(Boolean).join(', ') : locationId,
    dateRange: formatDateRange(start, end),
  }
}

/** True once the page has scrolled past `threshold` pixels. */
function useScrolled(threshold: number): boolean {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    let frame = 0

    function handleScroll() {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setScrolled(window.scrollY > threshold))
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()

    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', handleScroll)
    }
  }, [threshold])

  return scrolled
}
