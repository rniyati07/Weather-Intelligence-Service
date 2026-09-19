/**
 * Environment configuration — parsed and validated once, at module load.
 *
 * Reading `import.meta.env` directly from feature code spreads untyped string
 * access through the app and turns a missing variable into a runtime surprise
 * somewhere deep in a component. Validating here means a misconfigured deploy
 * fails immediately and says exactly what is wrong.
 *
 * Only `VITE_`-prefixed values exist in the bundle. The API key is deliberately
 * absent: it is held by the BFF and injected server-side (FDS constraint #3).
 */

import { z } from 'zod'

const envSchema = z.object({
  /**
   * Same-origin path the browser calls. Relative on purpose — an absolute URL
   * here would mean the browser talking to the API directly, which is exactly
   * what the BFF exists to prevent.
   */
  VITE_API_BASE_URL: z.string().min(1).default('/api/v1'),

  // A chat turn is the long pole, not narration: one request fans out to
  // geocoding, the weather providers, a live Overpass places search and two
  // Groq calls, all before a single response is written. 20s cut real turns
  // off mid-flight and surfaced as a spurious "connection may be slow".
  VITE_API_TIMEOUT_MS: z.coerce.number().int().positive().default(60_000),

  VITE_APP_VERSION: z.string().default('0.0.0'),

  VITE_ENABLE_QUERY_DEVTOOLS: z
    .enum(['true', 'false'])
    .default('false')
    .transform((value) => value === 'true'),
})

function parseEnv() {
  const result = envSchema.safeParse(import.meta.env)

  if (!result.success) {
    const issues = result.error.issues
      .map((issue) => `  · ${issue.path.join('.')}: ${issue.message}`)
      .join('\n')
    throw new Error(
      `Invalid frontend environment configuration:\n${issues}\n\nSee .env.example for the expected shape.`,
    )
  }

  return result.data
}

const parsed = parseEnv()

export const env = {
  apiBaseUrl: parsed.VITE_API_BASE_URL,
  apiTimeoutMs: parsed.VITE_API_TIMEOUT_MS,
  appVersion: parsed.VITE_APP_VERSION,
  enableQueryDevtools: parsed.VITE_ENABLE_QUERY_DEVTOOLS,
  isDev: import.meta.env.DEV,
  isProd: import.meta.env.PROD,
} as const

export type Env = typeof env
