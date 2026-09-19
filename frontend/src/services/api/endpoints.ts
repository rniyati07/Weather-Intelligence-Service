/**
 * One function per endpoint — the complete list of requests this app makes.
 *
 * Each returns `ApiResult<T>` (`{ data, metadata }`), because `metadata` drives
 * the metadata strip, the stale badge and the footer's rule-config version.
 * Errors are already normalised to `ApiError` by the response interceptor, so
 * nothing here catches: a rejection is always typed.
 *
 * No React, no caching, no retry policy. Those belong to `hooks/queries`.
 */

import { ENDPOINTS } from '@/constants/api'
import type {
  ApiEnvelope,
  ApiResult,
  BestDaysView,
  DateRangeParams,
  IsoDate,
  LanguageCode,
  LocationId,
  NarrativeView,
  PackingView,
  ProviderHealthView,
  RawWeatherView,
  WeatherIntelligence,
} from '@/types'
import type { AxiosRequestConfig } from 'axios'

import { apiClient, unwrap } from './client'

/**
 * Build a request config, omitting keys rather than setting them to
 * `undefined` — `exactOptionalPropertyTypes` treats those as different things,
 * and axios only accepts an actual `AbortSignal`.
 */
function config(params?: object, signal?: AbortSignal): AxiosRequestConfig {
  return { ...(params ? { params } : {}), ...(signal ? { signal } : {}) }
}

/** `GET /locations/{id}/intelligence` — API Spec §8.1. Powers the dashboard. */
export async function getIntelligence(
  locationId: LocationId,
  params: DateRangeParams,
  signal?: AbortSignal,
): Promise<ApiResult<WeatherIntelligence>> {
  const response = await apiClient.get<ApiEnvelope<WeatherIntelligence>>(
    ENDPOINTS.intelligence(locationId),
    config(params, signal),
  )
  return unwrap(response)
}

/**
 * `POST /locations/{id}/intelligence/narrative` — API Spec §8.5.
 *
 * A POST that computes rather than writes, which is why it is modelled as a
 * query. Fails with `503 SERVICE_DEGRADED` when the LLM is unavailable;
 * callers must confine that error to the AI Explanation card (FDS §13.3).
 */
export async function generateNarrative(
  locationId: LocationId,
  body: { startDate: IsoDate; endDate: IsoDate; language?: LanguageCode },
  signal?: AbortSignal,
): Promise<ApiResult<NarrativeView>> {
  const response = await apiClient.post<ApiEnvelope<NarrativeView>>(
    ENDPOINTS.narrative(locationId),
    body,
    config(undefined, signal),
  )
  return unwrap(response)
}

/** `GET /locations/{id}/weather/raw` — API Spec §8.4. Fetched lazily. */
export async function getRawWeather(
  locationId: LocationId,
  params: DateRangeParams,
  signal?: AbortSignal,
): Promise<ApiResult<RawWeatherView>> {
  const response = await apiClient.get<ApiEnvelope<RawWeatherView>>(
    ENDPOINTS.rawWeather(locationId),
    config(params, signal),
  )
  return unwrap(response)
}

/**
 * `GET /providers/health` — API Spec §8.6. **Operator only.**
 *
 * A consumer key gets `403` here, which the operator screen renders as an
 * explicit "operator key required" state rather than a generic error.
 */
export async function getProviderHealth(
  signal?: AbortSignal,
): Promise<ApiResult<ProviderHealthView>> {
  const response = await apiClient.get<ApiEnvelope<ProviderHealthView>>(
    ENDPOINTS.providerHealth(),
    config(undefined, signal),
  )
  return unwrap(response)
}

/* -------------------------------------------------------------------------
 * Available but unused by this UI.
 *
 * `tripSummary.bestDays` / `worstDays` / `overallPackingList` already arrive
 * with `GET /intelligence`, so calling these from the dashboard would burn
 * rate-limit budget for data already in hand (FDS §7.4, §7.5). They are
 * implemented because they are part of the contract and because a future
 * standalone packing share/print view is the natural consumer.
 * ---------------------------------------------------------------------- */

export async function getBestDays(
  locationId: LocationId,
  params: DateRangeParams,
  signal?: AbortSignal,
): Promise<ApiResult<BestDaysView>> {
  const response = await apiClient.get<ApiEnvelope<BestDaysView>>(
    ENDPOINTS.bestDays(locationId),
    config(params, signal),
  )
  return unwrap(response)
}

export async function getPacking(
  locationId: LocationId,
  params: DateRangeParams,
  signal?: AbortSignal,
): Promise<ApiResult<PackingView>> {
  const response = await apiClient.get<ApiEnvelope<PackingView>>(
    ENDPOINTS.packing(locationId),
    config(params, signal),
  )
  return unwrap(response)
}
