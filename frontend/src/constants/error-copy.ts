/**
 * Error-code → user-facing copy — FDS §13.2.
 *
 * The API's own `error.message` is never rendered: it is written for a
 * developer reading a log, not for a traveller deciding whether to retry. Every
 * entry here says in plain language what happened and what to do next, and
 * names no provider, no stack, no internal detail.
 *
 * `scope` is what a component reads to decide *where* to render the failure.
 * `card` scope exists for exactly one case and it is the most important
 * integration rule in the design: narration failing must never blank the
 * dashboard (FDS §7.2, §13.3).
 */

import type { AnyErrorCode } from '@/types'

export type ErrorScope = 'page' | 'card' | 'field' | 'section'

export interface ErrorPresentation {
  headline: string
  body: string
  /** Label for the primary action, or null when there is nothing useful to offer. */
  action: string | null
  scope: ErrorScope
}

const DEFAULT_PRESENTATION: ErrorPresentation = {
  headline: 'Something went wrong',
  body: 'An unexpected error occurred. Try again in a moment.',
  action: 'Try again',
  scope: 'page',
}

export const ERROR_PRESENTATION: Partial<Record<AnyErrorCode, ErrorPresentation>> = {
  VALIDATION_ERROR: {
    headline: 'Check your dates',
    body: 'One of the values sent with this request was not valid.',
    action: null,
    // Resolved against `details[].field` into an inline hint on that control.
    scope: 'field',
  },

  AUTHENTICATION_ERROR: {
    headline: 'Something went wrong on our end',
    body: "We couldn't authenticate the request. This is a configuration issue, not something you did.",
    action: 'Try again',
    scope: 'page',
  },

  AUTHORIZATION_ERROR: {
    headline: 'Operator access required',
    body: 'This page needs an operator key.',
    action: 'Go back',
    scope: 'page',
  },

  NOT_FOUND: {
    headline: "We couldn't find that",
    body: "This destination or page doesn't exist.",
    action: 'Go home',
    scope: 'page',
  },

  RATE_LIMITED: {
    headline: 'Too many requests',
    body: 'Limits keep the service responsive for everyone. This will clear on its own shortly.',
    action: 'Try again',
    scope: 'page',
  },

  PROVIDER_UNAVAILABLE: {
    headline: 'Weather data unavailable',
    body: "We can't reach our weather sources right now. Try again shortly.",
    action: 'Try again',
    scope: 'page',
  },

  UPSTREAM_TIMEOUT: {
    headline: 'That took too long',
    body: 'The request timed out before it completed. Try again.',
    action: 'Try again',
    scope: 'page',
  },

  /**
   * Narration failed; the intelligence did not. A degradation, not a failure —
   * and it must feel like one: muted surface, not red, confined to the card.
   */
  SERVICE_DEGRADED: {
    headline: 'AI Explanation unavailable',
    body: "The explanation couldn't be generated. All the intelligence below is unaffected.",
    action: 'Try again',
    scope: 'card',
  },

  INTERNAL_ERROR: {
    headline: 'Something went wrong',
    body: 'An unexpected error occurred. Quote the request id below if you contact support.',
    action: 'Try again',
    scope: 'page',
  },

  NETWORK_ERROR: {
    headline: "We couldn't reach the service",
    body: 'Check your connection and try again.',
    action: 'Try again',
    scope: 'page',
  },

  TIMEOUT: {
    headline: 'That took too long',
    body: 'The request timed out. Your connection may be slow right now.',
    action: 'Try again',
    scope: 'page',
  },

  CANCELLED: {
    headline: 'Request cancelled',
    body: 'The request was cancelled before it completed.',
    action: null,
    scope: 'section',
  },

  CLIENT_ERROR: DEFAULT_PRESENTATION,
}

/** Total lookup: an unrecognised code still yields sensible, non-alarming copy. */
export function getErrorPresentation(code: AnyErrorCode | undefined): ErrorPresentation {
  if (!code) return DEFAULT_PRESENTATION
  return ERROR_PRESENTATION[code] ?? DEFAULT_PRESENTATION
}
