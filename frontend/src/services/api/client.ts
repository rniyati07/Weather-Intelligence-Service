/**
 * The axios instance and its interceptors — the **only** module that knows HTTP.
 *
 * Two responsibilities, and nothing else:
 *
 *   1. Unwrap the response envelope centrally, so feature components receive
 *      `data` and never see `{ success, data, metadata, error }` (FDS §7.7).
 *   2. Normalise every failure into a typed `ApiError`, so callers branch on
 *      `error.code` rather than on a status number.
 *
 * Note what is absent: no API key. The browser calls a same-origin path and the
 * BFF attaches `X-API-Key` server-side (FDS constraint #3). If a key ever
 * appears in this file, the architecture has been broken.
 *
 * This module issues no requests on import. It configures the transport;
 * `endpoints.ts` describes the calls, and the query hooks make them.
 */

import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'

import { env } from '@/lib/env'
import type { AnyErrorCode, ApiEnvelope, ApiResult, ResponseMetadata } from '@/types'
import { ApiError, fromErrorBody } from './errors'

/** Status → client error code, for responses that never reached the envelope. */
const STATUS_FALLBACK_CODES: Record<number, AnyErrorCode> = {
  400: 'VALIDATION_ERROR',
  401: 'AUTHENTICATION_ERROR',
  403: 'AUTHORIZATION_ERROR',
  404: 'NOT_FOUND',
  408: 'UPSTREAM_TIMEOUT',
  429: 'RATE_LIMITED',
  500: 'INTERNAL_ERROR',
  502: 'PROVIDER_UNAVAILABLE',
  503: 'PROVIDER_UNAVAILABLE',
  504: 'UPSTREAM_TIMEOUT',
}

/** `Retry-After` may be seconds or an HTTP date. Both are honoured verbatim. */
function parseRetryAfter(header: unknown): number | undefined {
  if (typeof header !== 'string' || header.length === 0) return undefined

  const seconds = Number(header)
  if (Number.isFinite(seconds) && seconds >= 0) return seconds

  const timestamp = Date.parse(header)
  if (Number.isNaN(timestamp)) return undefined

  return Math.max(0, Math.round((timestamp - Date.now()) / 1000))
}

function isEnvelope(value: unknown): value is ApiEnvelope<unknown> {
  return typeof value === 'object' && value !== null && 'success' in value && 'metadata' in value
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: env.apiTimeoutMs,
  headers: { Accept: 'application/json' },
  // The BFF is same-origin, so cookies are not needed and are left off.
  withCredentials: false,
})

/* --------------------------------------------------------------------------
 * Request interceptor
 * ----------------------------------------------------------------------- */

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const headers = AxiosHeaders.from(config.headers)

  if (config.data !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  config.headers = headers
  return config
})

/* --------------------------------------------------------------------------
 * Response interceptor
 *
 * A `2xx` can still carry a degraded payload (`success: true, degraded: true`)
 * — that is a success and must render in full with a quiet badge, never an
 * error (API Spec §6, FDS §13.4).
 * ----------------------------------------------------------------------- */

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: unknown) => {
    if (axios.isCancel(error)) {
      return Promise.reject(
        new ApiError({ code: 'CANCELLED', message: 'Request cancelled.', cause: error }),
      )
    }

    if (error instanceof AxiosError) {
      const { response, code } = error

      if (code === 'ECONNABORTED' || code === 'ETIMEDOUT') {
        return Promise.reject(
          new ApiError({
            code: 'TIMEOUT',
            message: `Request timed out after ${String(env.apiTimeoutMs)}ms.`,
            cause: error,
          }),
        )
      }

      // No response at all: DNS failure, offline, CORS, connection refused.
      if (!response) {
        return Promise.reject(
          new ApiError({
            code: 'NETWORK_ERROR',
            message: 'Could not reach the service.',
            cause: error,
          }),
        )
      }

      const retryAfterSeconds = parseRetryAfter(response.headers['retry-after'])
      const body: unknown = response.data

      if (isEnvelope(body) && body.error) {
        return Promise.reject(
          fromErrorBody(body.error, {
            status: response.status,
            metadata: body.metadata,
            retryAfterSeconds,
          }),
        )
      }

      // A failure that never produced an envelope — a proxy error page, an
      // upstream gateway, a 404 on an unrouted path.
      return Promise.reject(
        new ApiError({
          code: STATUS_FALLBACK_CODES[response.status] ?? 'CLIENT_ERROR',
          message: `Request failed with status ${String(response.status)}.`,
          status: response.status,
          retryAfterSeconds,
          cause: error,
        }),
      )
    }

    return Promise.reject(
      new ApiError({
        code: 'CLIENT_ERROR',
        message: 'An unexpected error occurred.',
        cause: error,
      }),
    )
  },
)

/* --------------------------------------------------------------------------
 * Envelope unwrapping
 * ----------------------------------------------------------------------- */

/**
 * Unwrap a successful envelope into `{ data, metadata }`.
 *
 * `metadata` travels with the payload rather than being discarded, because the
 * metadata strip, the stale-data badge and the footer's rule-config version all
 * read from it.
 */
export function unwrap<TData>(response: AxiosResponse<ApiEnvelope<TData>>): ApiResult<TData> {
  const envelope = response.data

  if (!isEnvelope(envelope)) {
    throw new ApiError({
      code: 'CLIENT_ERROR',
      message: 'Response did not match the expected envelope contract.',
      status: response.status,
    })
  }

  // A 2xx carrying an error body should not happen, but trusting that it
  // cannot is how a null gets rendered as a verdict.
  if (envelope.error) {
    throw fromErrorBody(envelope.error, {
      status: response.status,
      metadata: envelope.metadata,
    })
  }

  if (envelope.data === null || envelope.data === undefined) {
    throw new ApiError({
      code: 'CLIENT_ERROR',
      message: 'Response contained no data.',
      status: response.status,
      requestId: envelope.metadata.requestId,
    })
  }

  return { data: envelope.data, metadata: envelope.metadata }
}

/** Metadata alone, for callers that need provenance without the payload. */
export function extractMetadata(response: AxiosResponse<ApiEnvelope<unknown>>): ResponseMetadata {
  return response.data.metadata
}
