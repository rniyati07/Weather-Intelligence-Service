import { useQueryClient } from '@tanstack/react-query'

import { Card } from '@/components/ui/card'
import { APP_NAME } from '@/constants/app'
import { env } from '@/lib/env'
import type { ApiResult, WeatherIntelligence } from '@/types'

/**
 * Which rule set produced your results — FDS §5.7.
 *
 * The rule-config version travels on every response's `metadata`, so it is read
 * from whatever intelligence result is already cached this session rather than
 * by issuing a request. A page explaining the product should not need to query
 * the product, and About consumes no API of its own (FDS §4.2).
 *
 * When nothing has been fetched yet there is genuinely no version to name, and
 * the page says so instead of inventing one.
 */
function useCachedRuleConfigVersion(): string | null {
  const queryClient = useQueryClient()

  const cached = queryClient.getQueriesData<ApiResult<WeatherIntelligence>>({
    queryKey: ['intelligence'],
  })

  for (const [, result] of cached) {
    const version = result?.metadata.ruleConfigVersion
    if (version) return version
  }

  return null
}

export function BuildProvenance() {
  const ruleConfigVersion = useCachedRuleConfigVersion()

  return (
    <Card className="flex flex-col divide-y divide-border">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 pb-4">
        <p className="text-body font-medium text-heading">Interface version</p>
        <p className="tabular text-body text-muted-foreground">v{env.appVersion}</p>
      </div>

      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 pt-4">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-body font-medium text-heading">Rule set</p>
          <p className="max-w-[46ch] text-body-sm text-muted-foreground">
            The version of the rules that produced your results. It is shown on every result page
            beneath the readings.
          </p>
        </div>
        <p className="tabular text-body text-muted-foreground">
          {ruleConfigVersion ?? 'Shown once you run a search'}
        </p>
      </div>

      <p className="pt-4 text-body-sm text-subtle-foreground">
        {APP_NAME} keeps no account and stores nothing about you on a server. Preferences, recent
        searches and packing checklists live in this browser.
      </p>
    </Card>
  )
}
