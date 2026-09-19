import { lazy, Suspense, type ComponentType, type LazyExoticComponent, type ReactNode } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router'

import { LoadingSkeleton } from '@/components/feedback/LoadingSkeleton'
import { MainLayout } from '@/components/layout/MainLayout'
import { PageContainer } from '@/components/layout/PageContainer'
import { ChatPage } from '@/features/chat/pages/ChatPage'
import { ROUTES } from '@/constants/routes'
import { RouteErrorBoundary } from './RouteErrorBoundary'

/**
 * Route table — FDS Revision 2 §4.1.
 *
 * Two layout groups, not one. Chat (`/`, `/chat/:conversationId`) is the
 * primary experience and owns its own full-height shell (`ChatShell`,
 * mounted inside `ChatPage`) — a `MainLayout` wrapper with a sticky nav and
 * a page footer would fight a chat surface that needs the full viewport and
 * its own composer pinned to the bottom. Every secondary/deep-dive screen
 * (`/trip`, `/plan`, `/settings`, `/about`, 404) keeps the original
 * `MainLayout` shell — skip link, nav, landmarks, footer — unchanged.
 *
 * `ChatPage` is bundled eagerly, same reasoning Revision 1 applied to the
 * old landing page: it is the app's entry point, and a spinner on first
 * paint would be worse than the few kilobytes saved by lazy-loading it.
 * Everything under `MainLayout` stays lazy.
 *
 * The URL is still the source of truth for a query — `/trip/:locationId`
 * carries `?start=&end=`, and `/chat/:conversationId` carries the thread id
 * — so a link is always shareable, deep-linkable and refresh-stable
 * (FDS §15.2).
 */

const PlannerPage = lazyPage(() => import('@/features/planner/pages/PlannerPage'), 'PlannerPage')
const ResultsPage = lazyPage(() => import('@/features/dashboard/pages/ResultsPage'), 'ResultsPage')
const SettingsPage = lazyPage(
  () => import('@/features/settings/pages/SettingsPage'),
  'SettingsPage',
)
const AboutPage = lazyPage(() => import('@/features/about/pages/AboutPage'), 'AboutPage')
const NotFoundPage = lazyPage(
  () => import('@/features/not-found/pages/NotFoundPage'),
  'NotFoundPage',
)

export const routes: RouteObject[] = [
  {
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: <ChatPage /> },
      { path: ROUTES.chat, element: <ChatPage /> },
    ],
  },
  {
    element: <MainLayout />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { path: ROUTES.plan, element: withSuspense(<PlannerPage />) },
      { path: ROUTES.trip, element: withSuspense(<ResultsPage />) },
      // Compat alias for a pre-Revision-2 `/results?location=&start=&end=` link.
      { path: ROUTES.results, element: withSuspense(<ResultsPage />) },
      { path: ROUTES.settings, element: withSuspense(<SettingsPage />) },
      { path: ROUTES.about, element: withSuspense(<AboutPage />) },
      { path: ROUTES.notFound, element: withSuspense(<NotFoundPage />) },
    ],
  },
]

export const router = createBrowserRouter(routes)

/**
 * Lazy-load a named export.
 *
 * `React.lazy` expects a default export; the codebase uses named exports so
 * that a renamed component is a compile error rather than a silent
 * `undefined`. This adapts between the two.
 */
function lazyPage<T extends string>(
  loader: () => Promise<Record<T, ComponentType>>,
  exportName: T,
): LazyExoticComponent<ComponentType> {
  return lazy(async () => {
    const module = await loader()
    return { default: module[exportName] }
  })
}

/**
 * Chunk-loading fallback.
 *
 * Shape-matched to a page rather than a bare spinner, and it renders inside the
 * shell — so the nav and footer stay put and only the content region changes.
 */
function withSuspense(element: ReactNode) {
  return (
    <Suspense
      fallback={
        <PageContainer>
          <LoadingSkeleton variant="card" count={4} label="Loading page" />
        </PageContainer>
      }
    >
      {element}
    </Suspense>
  )
}
