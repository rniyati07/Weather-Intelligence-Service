/** Product-level constants and copy that must stay consistent across screens. */

export const APP_NAME = 'Weather Intelligence Service'

/** Two-tone wordmark: "Weather" + "Intelligence". */
export const APP_WORDMARK = { primary: 'Weather', secondary: 'Intelligence' } as const

export const APP_TAGLINE = 'Should you travel? Get a clear verdict for any destination and dates.'

export const APP_DESCRIPTION =
  'Travel decision intelligence. Forecast inputs are probabilistic; verdicts come from a deterministic rule engine.'

/**
 * Mandatory labelling for the AI panel — Bible ADR-005/010 via FDS §1.3.
 * The product never implies the model formed a judgement: the title is
 * "AI Explanation", never "advice", "advisor" or "recommendation".
 */
export const AI_PANEL_TITLE = 'AI Explanation'

export const AI_DISCLOSURE =
  'Generated from the computed intelligence above. All numbers and rankings come from the deterministic engine.'

/** Shown wherever provenance needs stating in one line. */
export const DECISION_PROVENANCE =
  'Decisions are computed by a deterministic rule engine over normalized forecast readings. The AI explains the result — it never decides it.'

/** Rendered for a nullable value that the provider simply did not report. */
export const EMPTY_VALUE = '—'
