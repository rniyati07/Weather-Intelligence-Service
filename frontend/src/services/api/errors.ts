/**
 * Typed API errors.
 *
 * Every failure — transport, HTTP, or a malformed envelope — is normalised into
 * one `ApiError`. Feature code therefore branches on `error.code`, never on a
 * status number and never on an axios shape.
 *
 * That distinction is load-bearing. `PROVIDER_UNAVAILABLE` and
 * `SERVICE_DEGRADED` are both `503` and demand opposite responses: the first
 * means there is no intelligence to show and warrants a full-page error state;
 * the second means narration failed while *everything else succeeded*, so the
 * error must stay confined to the AI Explanation card (FDS §13.3).
 */

import { RETRYABLE_ERROR_CODES } from '@/constants/api'
import type { AnyErrorCode, ApiErrorBody, ApiErrorDetail, ResponseMetadata } from '@/types'

export interface ApiErrorOptions {
  code: AnyErrorCode
  /** The API's own message. Safe to log; never rendered raw to a user (FDS §13.1). */
  message: string
  status?: number | undefined
  details?: ApiErrorDetail[] | undefined
  /** Quoted in support-facing copy on every 4xx/5xx. */
  requestId?: string | undefined
  /** Seconds, from the `Retry-After` header on a 429. Honoured verbatim. */
  retryAfterSeconds?: number | undefined
  cause?: unknown
}

export class ApiError extends Error {
  readonly code: AnyErrorCode
  readonly status: number | undefined
  readonly details: ApiErrorDetail[]
  readonly requestId: string | undefined
  readonly retryAfterSeconds: number | undefined

  constructor(options: ApiErrorOptions) {
    super(options.message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'ApiError'
    this.code = options.code
    this.status = options.status
    this.details = options.details ?? []
    this.requestId = options.requestId
    this.retryAfterSeconds = options.retryAfterSeconds
  }

  /** Whether an automatic retry is appropriate. A 4xx client error never is. */
  get isRetryable(): boolean {
    return RETRYABLE_ERROR_CODES.includes(this.code)
  }

  /** Narration failed but the deterministic intelligence did not. Card-scoped. */
  get isNarrationDegraded(): boolean {
    return this.code === 'SERVICE_DEGRADED'
  }

  /** Field-level issues, indexed for inline hints on the offending control. */
  get fieldIssues(): Record<string, string> {
    return Object.fromEntries(this.details.map((detail) => [detail.field, detail.issue]))
  }

  static is(value: unknown): value is ApiError {
    return value instanceof ApiError
  }
}

/** Build an `ApiError` from a parsed error envelope. */
export function fromErrorBody(
  body: ApiErrorBody,
  context: {
    status?: number | undefined
    metadata?: ResponseMetadata | undefined
    retryAfterSeconds?: number | undefined
  } = {},
): ApiError {
  return new ApiError({
    code: body.code,
    message: body.message,
    status: context.status,
    details: body.details ?? undefined,
    requestId: context.metadata?.requestId,
    retryAfterSeconds: context.retryAfterSeconds,
  })
}

/**
 * Last-resort normaliser for anything that is not already an `ApiError` — a
 * thrown string, a DOM exception, a bug in our own code. Guarantees callers
 * never have to handle `unknown`.
 */
export function toApiError(value: unknown): ApiError {
  if (ApiError.is(value)) return value

  if (value instanceof Error) {
    return new ApiError({ code: 'CLIENT_ERROR', message: value.message, cause: value })
  }

  return new ApiError({
    code: 'CLIENT_ERROR',
    message: 'An unexpected error occurred.',
    cause: value,
  })
}
