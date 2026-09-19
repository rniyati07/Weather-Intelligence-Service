/**
 * Data hooks — the single seam between the UI and where data comes from.
 *
 * **The rule this folder exists to enforce:** no component, and no page, may
 * import from `@/services/api` for data. They ask a hook. That is what kept API
 * integration to these files instead of thirty components.
 *
 * Every hook returns the same narrow contract (`data` / `isPending` /
 * `isError` / `error` / `refetch`), so a call site cannot tell — and does not
 * care — that these are now real network queries.
 */

export { useConversationList } from './useConversationList'
export { useConversationThread } from './useConversationThread'
export { useGeocoding, useResolvedPlace } from './useGeocoding'
export { useIntelligence, type IntelligenceParams } from './useIntelligence'
export { useNarrative, type NarrativeParams } from './useNarrative'
export { useRawWeather, type RawWeatherParams } from './useRawWeather'
export { recordRecentSearch, useRecentSearches } from './useRecentSearches'
export { useSendChatMessage, type SendChatMessageVariables } from './useSendChatMessage'
export { useTripIntelligence } from './useTripIntelligence'
export type { LazyQueryOptions, QueryResult } from './types'
