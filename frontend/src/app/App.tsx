import { RouterProvider } from 'react-router'

import { router } from '@/routes/router'
import { AppProviders } from './AppProviders'

/**
 * Application root.
 *
 * Composition only — providers, then the router. Any logic that appears here
 * belongs in a feature or a hook.
 */
export function App() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
}
