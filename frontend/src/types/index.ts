/**
 * Shared type surface.
 *
 * These are hand-written from the API & Data Contract Specification (§9, §10)
 * because they are the contract the UI is designed against, and the comments
 * carry the "why" that a generated file cannot. Once `/openapi.json` is being
 * consumed for real (Phase 10.3), generate `services/api/schema.d.ts` from it
 * and have these types *narrow* the generated ones rather than duplicate them,
 * so contract drift fails the build instead of the browser.
 */

export type * from './api'
export type * from './common'
export type * from './location'
export type * from './narrative'
export type * from './providers'
export type * from './recent-search'
export type * from './trip'
export type * from './weather'

// Enums export runtime value arrays alongside their types, so they are not
// `export type`. `chat` similarly exports `parseTripContext` at runtime.
export * from './enums'
export * from './chat'
