import { QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, type ReactNode } from 'react'

import { TooltipProvider } from '@/components/ui/tooltip'
import { PreferencesProvider } from '@/context/PreferencesProvider'
import { ThemeProvider } from '@/context/ThemeProvider'
import { env } from '@/lib/env'
import { queryClient } from './query-client'

/**
 * Devtools are lazily imported so the package is never pulled into a
 * production bundle — the import itself only happens when the flag is on.
 */
const ReactQueryDevtools = lazy(async () => {
  const module = await import('@tanstack/react-query-devtools')
  return { default: module.ReactQueryDevtools }
})

/**
 * Every app-wide provider, in one place.
 *
 * Order matters and is not arbitrary: `ThemeProvider` is outermost because it
 * writes the theme class to `<html>` and everything below it renders against
 * those tokens. `TooltipProvider` is innermost because it only needs to wrap
 * the tree that contains tooltips, and it carries the shared 400ms hover delay
 * so every tooltip in the product opens on the same beat.
 *
 * Keeping this separate from `App` means a test can mount a component with the
 * real providers without dragging in the router.
 */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <PreferencesProvider>
          <TooltipProvider>{children}</TooltipProvider>
        </PreferencesProvider>

        {env.enableQueryDevtools ? (
          <Suspense fallback={null}>
            <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
          </Suspense>
        ) : null}
      </QueryClientProvider>
    </ThemeProvider>
  )
}
