/**
 * Response envelope, metadata and error contract — API Spec §6, §7, §9.12.
 *
 * Every response, success or failure, is wrapped in `ApiEnvelope`. The API
 * client unwraps it centrally and throws a typed error, so **feature
 * components never see the envelope** (FDS §7.7).
 */

import type { CacheStatus, ErrorCode } from './enums'
import type { IsoDateTime } from './common'

/** API Spec §9.12. Present on every response; deliberately provider-agnostic. */
export interface ResponseMetadata {
  /** Contract version, e.g. `"1.0"`. Diagnostics only — not displayed. */
  apiVersion: string
  /** Response time (UTC). Rendered as "updated 2m ago" in the metadata strip. */
  generatedAt: IsoDateTime
  /** Correlation id. Shown click-to-copy, and in every error state for support. */
  requestId: string
  /** Absent on error responses. `stale` raises the "showing last available data" badge. */
  cacheStatus?: CacheStatus | null
  /** Rule-config version behind the computed values. Footer + About. */
  ruleConfigVersion?: string | null
  /** `true` when data was served in a degraded mode. Content still renders in full. */
  degraded?: boolean | null
}

/** API Spec §7.2. Field-level issue, chiefly for validation. */
export interface ApiErrorDetail {
  /** Offending parameter or field name — maps to an inline hint on that control. */
  field: string
  /** What is wrong with it. */
  issue: string
}

/** API Spec §7.2. Never rendered raw to the user (FDS §13.1). */
export interface ApiErrorBody {
  code: ErrorCode
  message: string
  details?: ApiErrorDetail[] | null
}

/** API Spec §6. Exactly one of `data` / `error` is populated. */
export interface ApiEnvelope<TData> {
  success: boolean
  data: TData | null
  metadata: ResponseMetadata
  error: ApiErrorBody | null
}

/**
 * What a caller receives after the client unwraps a successful envelope.
 * `metadata` travels with the payload because the metadata strip, the stale
 * badge and the footer all read from it.
 */
export interface ApiResult<TData> {
  data: TData
  metadata: ResponseMetadata
}

/** Query parameters shared by the intelligence and raw-weather endpoints. */
export interface DateRangeParams {
  startDate: string
  endDate: string
}
