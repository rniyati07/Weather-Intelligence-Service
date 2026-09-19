import { Outlet } from 'react-router'

import { Footer } from './Footer'
import { Navbar } from './Navbar'

/**
 * The application shell — FDS §14.3.
 *
 * Semantic landmarks (`header` / `nav` in Navbar, `main` here, `footer` in
 * Footer) are what let a screen-reader user jump straight to content instead
 * of tabbing through navigation on every route.
 *
 * The skip link is the first focusable element on the page, which the FDS
 * requires on the dashboard specifically. Putting it in the shell rather than
 * on one route means it cannot be forgotten on the others.
 *
 * Rendered by the router as a layout route, so `<Outlet />` is the active page.
 */
export function MainLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <a
        href="#main-content"
        className="skip-link rounded-md bg-primary px-4 py-2 text-body-sm font-medium text-primary-foreground"
      >
        Skip to content
      </a>

      <Navbar />

      <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none">
        <Outlet />
      </main>

      <Footer />
    </div>
  )
}
