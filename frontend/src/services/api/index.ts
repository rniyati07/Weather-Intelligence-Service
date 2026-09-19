/**
 * API boundary.
 *
 * The only place in the app that knows HTTP exists. Nothing here runs on
 * import; every request is issued by a hook in `hooks/queries`.
 *
 * Import rule: components never import from here. Hooks do.
 *
 * User-facing error *copy* deliberately does not live here — it is content,
 * not transport, and sits in `constants/error-copy.ts` so a component can read
 * it without reaching into the HTTP layer.
 *
 * `schema.d.ts` is generated from the backend's `/openapi.json` (`npm run
 * generate:api`) and `contract.ts` binds it to the hand-written domain types,
 * so upstream drift fails the build.
 */

export { apiClient, extractMetadata, unwrap } from './client'
export { createConversation, getConversation, listConversations, sendChatMessage } from './chat'
export {
  generateNarrative,
  getBestDays,
  getIntelligence,
  getPacking,
  getProviderHealth,
  getRawWeather,
} from './endpoints'
export { ApiError, fromErrorBody, toApiError, type ApiErrorOptions } from './errors'
export { searchPlaces } from './geocoding'
export { retryDelay, shouldRetry } from './retry'
