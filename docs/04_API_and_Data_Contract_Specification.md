# Weather Intelligence Service — API & Data Contract Specification

## 1. Document Information

| Field | Value |
|---|---|
| **Document** | `docs/04_API_&_Data_Contract_Specification.md` |
| **Purpose** | Define the complete communication contract between API consumers and the backend. A frontend engineer should be able to integrate using only this document. |
| **Audience** | Frontend engineers, API consumers, backend developers, maintainers, integration partners (e.g., the future TravelOS planner). |
| **Version** | 1.0 |
| **Status** | Approved for implementation |
| **Dependencies** | Requires an issued API key (§3). Backend depends on external weather providers (§4), which are internal-only. |
| **Related documents** | `01_Project_Bible.md`, `02_Product_Requirements_Document.md`, `03_Technical_Design_Document.md` (all v1.0, approved — not modified or restated here). |

**Scope.** This document specifies only the API interface and data contracts: endpoints, request/response schemas, validation, authentication, errors, enumerations, versioning, and the internal provider integration layer. Product rationale, architecture, and testing live in the referenced documents and are not repeated.

**Conventions.**
- All examples use `application/json`.
- All dates are ISO-8601 calendar dates (`YYYY-MM-DD`); all timestamps are ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`).
- Units are metric (§5).
- Field names are `camelCase`; enum values are `snake_case` or `UPPER_SNAKE_CASE` as specified per enum (§10).

---

## 2. API Design Principles

| Principle | Contract implication |
|---|---|
| **RESTful design** | Resources are nouns (`locations`, `intelligence`, `providers`); HTTP verbs express intent (`GET` reads, `POST` triggers narration). |
| **Stateless communication** | Every request is self-contained and carries its own auth. No server-side session state; identical requests are independently serviceable. |
| **JSON payloads** | Requests and responses are JSON. `Content-Type: application/json` and `Accept: application/json`. |
| **Resource naming** | Hierarchical, plural collections: `/locations/{locationId}/intelligence`. Sub-resources for derived views (`/best-days`, `/packing`, `/narrative`). |
| **Consistent response format** | Every response — success or failure — uses one envelope (§6): `success`, `data`, `metadata`, `error`. |
| **Versioning** | Version in the URI path (`/api/v1`). See §12. |
| **Backward compatibility** | Additive changes only within a major version; new fields and new enum values are non-breaking (§12). |
| **Deterministic responses** | For identical inputs and the same `ruleConfigVersion`, all computed fields are identical. The optional `narrative` text is the only non-deterministic element, and it is served by a separate endpoint. |
| **Provider independence** | Responses never reveal which external provider supplied the underlying weather. Provider identity is an internal concern (§4). |

**API design philosophy.** The contract exposes *travel intelligence*, not raw meteorology and not implementation detail. Consumers depend on a stable, provider-agnostic shape; the backend is free to change providers, caching, or models without breaking clients, provided this contract holds.

---

## 3. Authentication & Authorization

| Aspect | Specification |
|---|---|
| **Authentication method** | API key (per-consumer), issued out of band. |
| **Authorization header** | `X-API-Key: <api_key>` on every request. (An API key identifies and authorizes the consumer; there are no per-user roles in v1.) |
| **Content-Type** | `application/json` (required on requests with a body). |
| **Accept** | `application/json` (recommended; JSON is returned regardless). |
| **Transport** | HTTPS required. Requests over plain HTTP are rejected. |
| **Security expectations** | Keys are secrets: never embed a key in frontend source shipped to end users. Browser clients must call through a backend-for-frontend or proxy that injects the key. Keys may be rotated; treat them as opaque. |
| **Missing/invalid key** | `401` with `AUTHENTICATION_ERROR` (§7). |
| **Key lacks access to a resource** | `403` with `AUTHORIZATION_ERROR` (reserved; not used for role logic in v1). |
| **Future authentication support** | OAuth2 / OIDC and per-tenant scoping are anticipated for a later enterprise version and will be additive (a new auth scheme alongside API keys), not a breaking replacement. |

---

## 4. External Provider Integrations (internal backend layer)

> **This section is for backend developers and maintainers only.** It documents internal implementation dependencies. **None of it appears in the public API contract.** Provider-specific request formats and response schemas are never exposed to API consumers, and no weather-data response reveals which provider was used.

The backend integrates four external weather services. Three supply **forecast/current** data; one supplies **historical/baseline** data. All are accessed behind a uniform internal `WeatherProvider` interface and normalized to one internal model before any processing.

### 4.1 Providers

#### 4.1.1 OpenWeather
| Field | Value |
|---|---|
| Purpose | Forecast and current conditions (forecast provider). |
| Base URL | `https://api.openweathermap.org/data/2.5` |
| Authentication | API key passed as the `appid` query parameter. |
| API key requirement | **Required** (`OPENWEATHER_API_KEY`). |
| Supported features | Current conditions, short/medium-range forecast, temperature, precipitation, wind, condition codes. |
| Expected usage | Forecast-class fallback provider. |
| Known limitations | Free-tier request quotas and limited forecast horizon; quotas/pricing vary by plan — consult the provider's current documentation. |
| Internal normalization notes | Map OpenWeather numeric condition codes → internal `WeatherCondition`; convert to metric units; map fields to the internal reading model. |

#### 4.1.2 WeatherAPI
| Field | Value |
|---|---|
| Purpose | Forecast and current conditions (forecast provider). |
| Base URL | `http://api.weatherapi.com/v1` (HTTPS used in practice). |
| Authentication | API key passed as the `key` query parameter. |
| API key requirement | **Required** (`WEATHERAPI_KEY`). |
| Supported features | Current, forecast, and limited historical; condition text/codes, precipitation, wind. |
| Expected usage | Forecast-class fallback provider. |
| Known limitations | Free-tier call limits and reduced forecast days on lower tiers; consult current provider docs for quotas. |
| Internal normalization notes | Map WeatherAPI condition codes → internal `WeatherCondition`; normalize units and field names. |

#### 4.1.3 Open-Meteo
| Field | Value |
|---|---|
| Purpose | Forecast and current conditions (forecast provider). |
| Base URL | `https://api.open-meteo.com` |
| Authentication | **None** — no API key required for standard non-commercial use. |
| API key requirement | **Not required.** |
| Supported features | Current and multi-day forecast; temperature, precipitation probability, wind, WMO weather codes. |
| Expected usage | **Primary forecast provider** (no key, low friction). |
| Known limitations | Fair-use limits on the free endpoint; no per-consumer key means shared-quota behavior; historical data is served by a separate archive interface, not this base. |
| Internal normalization notes | Map WMO weather codes → internal `WeatherCondition`; data is already metric-friendly. |

#### 4.1.4 Meteostat
| Field | Value |
|---|---|
| Purpose | Historical and climate-baseline data (historical provider). |
| Base URL | `https://meteostat.net` (hosted API endpoint configured per environment). |
| Authentication | API key (hosted API). |
| API key requirement | **Required** (`METEOSTAT_API_KEY`). |
| Supported features | Historical daily/station observations and climate normals. |
| Expected usage | **Historical/baseline class only** — fuels typical-weather baselines and anomaly comparisons (a future capability). Not used for forward forecasts. |
| Known limitations | Not a real-time forecast source; station coverage and historical depth vary by location. |
| Internal normalization notes | Normalize historical observations to the same internal reading model; used for baseline comparison, never as a forecast fallback. |

### 4.2 Provider layer behavior

| Concern | Specification |
|---|---|
| **Provider Abstraction Layer** | All providers implement one internal `WeatherProvider` interface. Downstream processing sees only the normalized internal model — never a provider payload. |
| **Provider Registry** | Central registry holding each provider's adapter, data class (forecast vs historical), priority, active flag, and last health result. |
| **Provider Selection Strategy** | Select by **data class first** (forecast requests never route to the historical provider and vice-versa), then by **priority order**, then by **health**. |
| **Provider Priority** | Forecast order (default, configurable): Open-Meteo → OpenWeather → WeatherAPI. Historical: Meteostat. |
| **Fallback Strategy** | On a forecast provider failure/timeout, advance to the next forecast provider in priority order. If all forecast providers fail, serve last-known stored data (marked stale) or return a degraded response (§7). |
| **Timeout Handling** | Per-call hard timeout; on expiry the call is treated as a failure and fallback advances. No request blocks indefinitely. |
| **Retry Policy** | Minimal, bounded retry on transient network errors only; no retry on `4xx`. Retries do not stack with fallback (brief same-provider retry, then fall back). |
| **Response Normalization** | Every provider payload is validated and mapped to the internal reading model (units, condition vocabulary, field names) before persistence or computation. Field completeness after normalization informs downstream confidence scoring. |
| **Standard Error Mapping** | Provider errors map to internal error codes: upstream timeout → `UPSTREAM_TIMEOUT`; all providers exhausted → `PROVIDER_UNAVAILABLE` / `SERVICE_DEGRADED`; provider `4xx`/auth issues are internal and never surfaced verbatim to consumers. |
| **Configuration** | API keys and priority/timeout/retry settings are environment-configured (`OPENWEATHER_API_KEY`, `WEATHERAPI_KEY`, `METEOSTAT_API_KEY`; Open-Meteo needs none). Priority order and timeouts are tunable without code changes. |

**Contract guarantee:** changing provider set, priority, or availability never changes the public response shape. Consumers cannot observe provider identity through any weather-data endpoint.

---

## 5. Common Request Standards

| Standard | Specification |
|---|---|
| **Base URL** | `https://{host}/api/v1` |
| **API version** | `v1` (in the path). See §12. |
| **Required headers** | `X-API-Key: <api_key>`; `Accept: application/json`. `Content-Type: application/json` on requests with a body. |
| **Content types** | Request and response bodies are `application/json`. |
| **Date format** | ISO-8601 calendar date `YYYY-MM-DD` for `startDate` / `endDate`. |
| **Timezone handling** | Date ranges are interpreted in the **location's local timezone** (weather is inherently local). Response timestamps (`generatedAt`) are UTC. |
| **Units** | Metric and fixed in v1: temperature °C, wind speed km/h, precipitation probability `0.0–1.0`, precipitation amount mm. (An optional imperial mode is a documented future extension; not active in v1.) |
| **Coordinate format** | Decimal degrees. Latitude `[-90, 90]`, longitude `[-180, 180]`. |
| **Location identifier** | `locationId` path parameter. In v1 it is a coordinate pair `"{lat},{lon}"` (URL-encoded), e.g. `15.2993,74.1240`. Resolving a place name to coordinates (geocoding) is a **client responsibility** and is outside this service's scope. |
| **Query parameters** | `startDate`, `endDate` (required on intelligence/raw endpoints). `language` (optional, narration only). |
| **Optional parameters** | Unknown query parameters are ignored, not rejected. |
| **Pagination** | Not applicable. Responses are bounded by the requested date range (§11 caps the range), so no pagination is defined in v1. |
| **Filtering** | Not applicable in v1. |
| **Sorting** | Not applicable. `dailyIntelligence` is always returned in ascending date order. |

---

## 6. Common Response Standards

Every response uses one envelope. Exactly one of `data` / `error` is populated; the other is `null`.

| Field | Type | Description |
|---|---|---|
| `success` | boolean | `true` on a `2xx` outcome (including degraded success), `false` otherwise. |
| `data` | object \| null | The result payload on success; `null` on error. |
| `metadata` | object | Present on every response (§9, `Metadata`). Request-level, provider-agnostic. |
| `error` | object \| null | The error object (§7) on failure; `null` on success. |

**Success example:**
```json
{
  "success": true,
  "data": { "...": "endpoint-specific payload" },
  "metadata": {
    "apiVersion": "1.0",
    "generatedAt": "2026-07-21T10:00:00Z",
    "requestId": "req_9f2c1a7b",
    "cacheStatus": "hit",
    "ruleConfigVersion": "2026.07",
    "degraded": false
  },
  "error": null
}
```

**Degraded success example** (valid data served despite a provider issue — note `success: true`, `degraded: true`):
```json
{
  "success": true,
  "data": { "...": "intelligence built from last-known data" },
  "metadata": {
    "apiVersion": "1.0",
    "generatedAt": "2026-07-21T10:00:00Z",
    "requestId": "req_5b1d0e33",
    "cacheStatus": "stale",
    "ruleConfigVersion": "2026.07",
    "degraded": true
  },
  "error": null
}
```

**Error example:**
```json
{
  "success": false,
  "data": null,
  "metadata": {
    "apiVersion": "1.0",
    "generatedAt": "2026-07-21T10:00:00Z",
    "requestId": "req_3a7e22c9"
  },
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "startDate must be on or before endDate.",
    "details": [
      { "field": "startDate", "issue": "startDate is after endDate" }
    ]
  }
}
```

---

## 7. Error Contract

### 7.1 HTTP status codes

| Status | Meaning | `error.code` |
|---|---|---|
| `200 OK` | Success (including degraded success, with `metadata.degraded = true`). | — |
| `400 Bad Request` | Malformed or invalid parameters/body. | `VALIDATION_ERROR` |
| `401 Unauthorized` | Missing/invalid API key. | `AUTHENTICATION_ERROR` |
| `403 Forbidden` | Key not permitted for the resource (reserved). | `AUTHORIZATION_ERROR` |
| `404 Not Found` | Unknown route or unresolvable location. | `NOT_FOUND` |
| `429 Too Many Requests` | Consumer rate limit exceeded. | `RATE_LIMITED` |
| `500 Internal Server Error` | Unexpected server fault. | `INTERNAL_ERROR` |
| `503 Service Unavailable` | All weather providers unavailable and no usable stored data. | `PROVIDER_UNAVAILABLE` / `SERVICE_DEGRADED` |

### 7.2 Standard error object

| Field | Type | Required | Nullable | Description |
|---|---|---|---|---|
| `code` | string (enum `ErrorCode`) | yes | no | Stable machine-readable error code. |
| `message` | string | yes | no | Human-readable summary. Safe to log; never contains internal/provider detail. |
| `details` | array<ErrorDetail> | no | yes | Field-level issues (chiefly for validation). |

**`ErrorDetail`:**
| Field | Type | Description |
|---|---|---|
| `field` | string | Offending parameter/field name. |
| `issue` | string | What is wrong with it. |

### 7.3 Error categories

| Category | Code | Typical cause | Client action |
|---|---|---|---|
| Validation | `VALIDATION_ERROR` | bad dates/coords/range | fix request; do not retry unchanged |
| Authentication | `AUTHENTICATION_ERROR` | missing/invalid key | fix credentials |
| Authorization | `AUTHORIZATION_ERROR` | key lacks access (reserved) | contact provider of key |
| Provider failure | `PROVIDER_UNAVAILABLE` | all upstream providers down, no stored data | retry later with backoff |
| Timeout | `UPSTREAM_TIMEOUT` | upstream slow beyond timeout | retry with backoff |
| Rate limit | `RATE_LIMITED` | quota exceeded | honor `Retry-After`, back off |
| Degraded | `SERVICE_DEGRADED` | partial capability only | retry later; data may be stale |
| Internal | `INTERNAL_ERROR` | unexpected fault | retry once; then report `requestId` |

> Note: `PROVIDER_UNAVAILABLE`, `UPSTREAM_TIMEOUT`, and `SERVICE_DEGRADED` describe *the service's* upstream state generically. They never name or expose a specific external provider.

---

## 8. REST API Specification

Base URL for all endpoints: `https://{host}/api/v1`. All endpoints require `X-API-Key`. Common headers and the response envelope (§6) apply to every endpoint and are not repeated per-endpoint.

### 8.1 Get Weather Intelligence

| | |
|---|---|
| **Purpose** | Full deterministic weather intelligence (per-day + trip summary) for a location and date range. **No narration.** |
| **Method / Endpoint** | `GET /locations/{locationId}/intelligence` |
| **Authentication** | `X-API-Key` (required) |
| **Path params** | `locationId` — coordinate id `"{lat},{lon}"` |
| **Query params** | `startDate` (required, `YYYY-MM-DD`), `endDate` (required, `YYYY-MM-DD`) |
| **Request body** | none |

**Validation rules:** valid coordinate `locationId`; both dates present and well-formed; `startDate ≤ endDate`; range within limits (§11).
**Business rules:** `data.narrative` is always `null` on this endpoint (narration is a separate call). Computed fields are deterministic for the same inputs and `ruleConfigVersion`.

**Success response (`200`):** `data` = `WeatherIntelligence` (§9.1), `narrative = null`.

**Failure responses:** `400` invalid params; `401` bad key; `404` unresolvable location; `429` rate limited; `503` all providers down and no stored data.

**Example request:**
```http
GET /api/v1/locations/15.2993,74.1240/intelligence?startDate=2026-08-01&endDate=2026-08-05
Host: api.example.com
X-API-Key: sk_live_xxx
Accept: application/json
```

**Example success response:** see §13 (Successful Response).
**Example error response:** see §13 (Validation Error).

---

### 8.2 Get Best & Worst Days

| | |
|---|---|
| **Purpose** | Trip-level best/worst day view (a projection of the trip summary). |
| **Method / Endpoint** | `GET /locations/{locationId}/intelligence/best-days` |
| **Auth / Headers** | `X-API-Key` |
| **Query params** | `startDate` (required), `endDate` (required) |
| **Request body** | none |

**Validation:** identical to §8.1.
**Business rules:** returns the ranking subset of the trip summary; derived from the same computation as §8.1.

**Success (`200`):** `data` = `BestDaysView` (§9.7).
**Failures:** as §8.1.

**Example request:**
```http
GET /api/v1/locations/15.2993,74.1240/intelligence/best-days?startDate=2026-08-01&endDate=2026-08-05
X-API-Key: sk_live_xxx
```

---

### 8.3 Get Packing Recommendations

| | |
|---|---|
| **Purpose** | Aggregated trip packing list (a projection of the trip summary). |
| **Method / Endpoint** | `GET /locations/{locationId}/intelligence/packing` |
| **Auth / Headers** | `X-API-Key` |
| **Query params** | `startDate` (required), `endDate` (required) |
| **Request body** | none |

**Validation:** identical to §8.1.
**Success (`200`):** `data` = `PackingView` (§9.8).
**Failures:** as §8.1.

**Example request:**
```http
GET /api/v1/locations/15.2993,74.1240/intelligence/packing?startDate=2026-08-01&endDate=2026-08-05
X-API-Key: sk_live_xxx
```

---

### 8.4 Get Raw Weather (normalized)

| | |
|---|---|
| **Purpose** | Provider-normalized daily weather readings, without intelligence processing. |
| **Method / Endpoint** | `GET /locations/{locationId}/weather/raw` |
| **Auth / Headers** | `X-API-Key` |
| **Query params** | `startDate` (required), `endDate` (required) |
| **Request body** | none |

**Validation:** identical to §8.1.
**Business rules:** readings are the internal normalized model (§9.9). **No provider is identified.**
**Success (`200`):** `data` = `{ location, period, readings: RawWeatherReading[] }`.
**Failures:** as §8.1.

**Example request:**
```http
GET /api/v1/locations/15.2993,74.1240/weather/raw?startDate=2026-08-01&endDate=2026-08-05
X-API-Key: sk_live_xxx
```

---

### 8.5 Generate Narrative (optional AI narration)

| | |
|---|---|
| **Purpose** | Natural-language restatement of the deterministic intelligence for a location and range. Never alters computed values. |
| **Method / Endpoint** | `POST /locations/{locationId}/intelligence/narrative` |
| **Auth / Headers** | `X-API-Key`; `Content-Type: application/json` |
| **Path params** | `locationId` |
| **Request body** | `NarrativeRequest` (§9.10): `{ startDate, endDate, language? }` |

**Validation:** valid `locationId`; `startDate`/`endDate` present, well-formed, `startDate ≤ endDate`, within limits; `language` (optional) a supported code.
**Business rules:** the backend uses the deterministic intelligence for the given location/range and narrates it. If the AI layer is disabled, times out, or fails, a deterministic templated narrative is returned with `fallbackUsed = true`; the call still returns `200`. `narrative` is the only content produced here; no computed value is created or changed.

**Success (`200`):** `data` = `{ location, period, narrative }` where `narrative` is a `Narrative` object (§9.6).
**Failures:** `400` invalid body; `401` bad key; `404` unresolvable location; `429` rate limited. (AI failure does **not** produce an error — it produces a fallback narrative.)

**Example request:**
```http
POST /api/v1/locations/15.2993,74.1240/intelligence/narrative
X-API-Key: sk_live_xxx
Content-Type: application/json

{ "startDate": "2026-08-01", "endDate": "2026-08-05", "language": "en" }
```

**Example response / fallback example:** see §13 (AI Narration).

---

### 8.6 Provider Health (operational / maintainer endpoint)

| | |
|---|---|
| **Purpose** | Report upstream provider availability. **Operational endpoint for maintainers/operators**, not part of the provider-independent weather contract. It is the one endpoint that names providers, by design, for operators; it may be access-restricted. |
| **Method / Endpoint** | `GET /providers/health` |
| **Auth / Headers** | `X-API-Key` (operator key) |
| **Query params** | none |
| **Request body** | none |

**Success (`200`):** `data` = `{ providers: ProviderHealth[] }` (§9.11).
**Failures:** `401` bad key; `500` internal.

**Example request:**
```http
GET /api/v1/providers/health
X-API-Key: sk_ops_xxx
```

**Example success response:**
```json
{
  "success": true,
  "data": {
    "providers": [
      { "provider": "open-meteo", "status": "available", "lastCheckedAt": "2026-07-21T09:59:00Z" },
      { "provider": "openweather", "status": "available", "lastCheckedAt": "2026-07-21T09:59:00Z" },
      { "provider": "weatherapi", "status": "degraded", "lastCheckedAt": "2026-07-21T09:58:30Z" },
      { "provider": "meteostat", "status": "available", "lastCheckedAt": "2026-07-21T09:55:00Z" }
    ]
  },
  "metadata": { "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:00Z", "requestId": "req_health_01" },
  "error": null
}
```

---

## 9. Complete Data Contract

All objects below are provider-independent. Types: `string`, `number` (decimal), `integer`, `boolean`, `array<T>`, `object`, ISO date/datetime strings, and named enums (§10).

### 9.1 `WeatherIntelligence` (root payload of §8.1)
| Field | Type | Required | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|---|
| `location` | `Location` | yes | no | — | — | Resolved location. |
| `period` | `Period` | yes | no | — | — | Requested date range. |
| `dailyIntelligence` | array<`DailyIntelligence`> | yes | no | — | ascending by date | One entry per day in range. |
| `tripSummary` | `TripSummary` | yes | no | — | — | Trip-level rollup. |
| `narrative` | `Narrative` | no | yes | `null` | — | Always `null` on §8.1; populated only by §8.5. |

**Example:** see §13 (Successful Response).

### 9.2 `Location`
| Field | Type | Required | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|---|
| `id` | string | yes | no | — | `"lat,lon"` in v1 | Canonical location identifier. |
| `name` | string | no | yes | `null` | — | Human-readable name if known. |
| `latitude` | number | yes | no | — | `[-90, 90]` | Decimal degrees. |
| `longitude` | number | yes | no | — | `[-180, 180]` | Decimal degrees. |

### 9.3 `Period`
| Field | Type | Required | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `startDate` | string (date) | yes | no | `YYYY-MM-DD` | Inclusive start. |
| `endDate` | string (date) | yes | no | `YYYY-MM-DD`, `≥ startDate` | Inclusive end. |

### 9.4 `DailyIntelligence`
| Field | Type | Required | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `date` | string (date) | yes | no | `YYYY-MM-DD` | The day. |
| `summary` | `DailySummary` | yes | no | — | Weather summary. |
| `riskAssessment` | `RiskAssessment` | yes | no | — | Risk level + factors. |
| `activitySuitability` | array<`ActivitySuitability`> | yes | no | — | Score per activity category. |
| `packingRecommendations` | array<string> | yes | no | — | Items suggested for the day. |
| `travelAdvisory` | string (enum `TravelAdvisory`) | yes | no | — | Day-level advisory signal. |

#### 9.4.1 `DailySummary`
| Field | Type | Required | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `tempMinC` | number | yes | no | — | Min temperature (°C). |
| `tempMaxC` | number | yes | no | `≥ tempMinC` | Max temperature (°C). |
| `precipitationProbability` | number | yes | no | `0.0–1.0` | Chance of precipitation. |
| `windSpeedKph` | number | yes | no | `≥ 0` | Wind speed (km/h). |
| `condition` | string (enum `WeatherCondition`) | yes | no | — | Normalized condition. |

#### 9.4.2 `RiskAssessment`
| Field | Type | Required | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `overallRiskLevel` | string (enum `RiskLevel`) | yes | no | — | Day risk level. |
| `riskFactors` | array<`RiskFactor`> | yes | no | may be empty | Contributing factors. |

#### 9.4.3 `RiskFactor`
| Field | Type | Required | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `type` | string (enum `RiskFactorType`) | yes | no | — | Factor category. |
| `severity` | string (enum `Severity`) | yes | no | — | Factor severity. |
| `description` | string | yes | no | — | Human-readable explanation. |
| `rule` | string | yes | no | — | Identifier of the rule that produced this factor (explainability). |

#### 9.4.4 `ActivitySuitability`
| Field | Type | Required | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `activity` | string (enum `ActivityCategory`) | yes | no | — | Activity category. |
| `score` | integer | yes | no | `0–100` | Higher = more suitable. |

### 9.5 `TripSummary`
| Field | Type | Required | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `bestDays` | array<string (date)> | yes | no | subset of range | Best day(s) to travel. |
| `worstDays` | array<string (date)> | yes | no | subset of range | Worst day(s). |
| `overallPackingList` | array<string> | yes | no | — | Aggregated trip packing list. |
| `overallRiskLevel` | string (enum `RiskLevel`) | yes | no | — | Worst-case trip risk. |
| `tripSuitabilityScore` | integer | yes | no | `0–100` | Overall trip quality for likely activities. |
| `travelConfidence` | number | yes | no | `0.0–1.0` | Confidence in the assessment (forecast horizon, source agreement, data completeness). |

### 9.6 `Narrative`
| Field | Type | Required | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|---|
| `generatedByLLM` | boolean | yes | no | — | — | `false` when a templated fallback was used. |
| `summaryText` | string | yes | no | — | length-capped | The narration text. |
| `modelUsed` | string | no | yes | `null` | — | Model identifier, or `null` on fallback. |
| `fallbackUsed` | boolean | yes | no | — | — | `true` if the deterministic template was used. |

### 9.7 `BestDaysView` (payload of §8.2)
| Field | Type | Required | Nullable | Description |
|---|---|---|---|---|
| `location` | `Location` | yes | no | Resolved location. |
| `period` | `Period` | yes | no | Range. |
| `bestDays` | array<string (date)> | yes | no | Best day(s). |
| `worstDays` | array<string (date)> | yes | no | Worst day(s). |
| `overallRiskLevel` | string (enum `RiskLevel`) | yes | no | Trip risk. |

### 9.8 `PackingView` (payload of §8.3)
| Field | Type | Required | Nullable | Description |
|---|---|---|---|---|
| `location` | `Location` | yes | no | Resolved location. |
| `period` | `Period` | yes | no | Range. |
| `overallPackingList` | array<string> | yes | no | Aggregated list. |

### 9.9 `RawWeatherReading` (element of §8.4)
| Field | Type | Required | Nullable | Constraints | Description |
|---|---|---|---|---|---|
| `date` | string (date) | yes | no | `YYYY-MM-DD` | Reading day. |
| `tempMinC` | number | yes | no | — | Min temp (°C). |
| `tempMaxC` | number | yes | no | `≥ tempMinC` | Max temp (°C). |
| `precipitationProbability` | number | yes | no | `0.0–1.0` | Precip chance. |
| `precipitationMm` | number | no | yes | `≥ 0` | Precip amount (mm), if available. |
| `windSpeedKph` | number | yes | no | `≥ 0` | Wind (km/h). |
| `humidity` | number | no | yes | `0.0–1.0` | Relative humidity, if available. |
| `condition` | string (enum `WeatherCondition`) | yes | no | — | Normalized condition. |

### 9.10 `NarrativeRequest` (request body of §8.5)
| Field | Type | Required | Nullable | Default | Constraints | Description |
|---|---|---|---|---|---|---|
| `startDate` | string (date) | yes | no | — | `YYYY-MM-DD` | Range start. |
| `endDate` | string (date) | yes | no | — | `≥ startDate` | Range end. |
| `language` | string | no | yes | `"en"` | supported code | Narration language (v1 supports `en`). |

### 9.11 `ProviderHealth` (element of §8.6 — operational only)
| Field | Type | Required | Nullable | Description |
|---|---|---|---|---|
| `provider` | string | yes | no | Internal provider name (operator-facing only). |
| `status` | string (enum `ProviderStatus`) | yes | no | Availability. |
| `lastCheckedAt` | string (datetime) | yes | no | Last health check (UTC). |

### 9.12 `Metadata` (on every response envelope)
| Field | Type | Required | Nullable | Description |
|---|---|---|---|---|
| `apiVersion` | string | yes | no | Contract version, e.g. `"1.0"`. |
| `generatedAt` | string (datetime) | yes | no | Response time (UTC). |
| `requestId` | string | yes | no | Correlation id for support/tracing. |
| `cacheStatus` | string (enum `CacheStatus`) | no | yes | Present on data responses. |
| `ruleConfigVersion` | string | no | yes | Rule-config version behind computed values. |
| `degraded` | boolean | no | yes | `true` when data was served in a degraded mode. |

> **Provider independence:** `Metadata` intentionally contains **no** provider identity. Provider names appear only in the operational `/providers/health` payload (§9.11).

### 9.13 `Error` — see §7.2.

---

## 10. Enumerations

| Enum | Allowed values | Meaning / usage |
|---|---|---|
| **`RiskLevel`** | `low`, `moderate`, `high` | Severity of travel disruption/hazard. Used on `RiskAssessment.overallRiskLevel`, `TripSummary.overallRiskLevel`. |
| **`Severity`** | `low`, `moderate`, `high` | Severity of an individual `RiskFactor`. |
| **`TravelAdvisory`** | `proceed`, `caution`, `avoid` | Day-level guidance. Derived from day risk: `low → proceed`, `moderate → caution`, `high → avoid`. |
| **`ActivityCategory`** | `outdoor_sightseeing`, `beach`, `indoor_museum` | Fixed v1 set for suitability scoring. Config-defined; new categories are additive (§12). |
| **`RiskFactorType`** | `heat`, `cold`, `rain`, `storm`, `wind` | Category of a contributing risk factor (v1 taxonomy; config-defined, extensible additively). |
| **`WeatherCondition`** | `clear`, `partly_cloudy`, `cloudy`, `rain`, `heavy_rain`, `thunderstorm`, `snow`, `fog` | Normalized internal condition vocabulary (provider codes map into this set). |
| **`CacheStatus`** | `hit`, `miss`, `stale` | Freshness of the served data. |
| **`ProviderStatus`** | `available`, `degraded`, `unavailable` | Operational provider state (`/providers/health` only). |
| **`ErrorCode`** | `VALIDATION_ERROR`, `AUTHENTICATION_ERROR`, `AUTHORIZATION_ERROR`, `NOT_FOUND`, `RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, `UPSTREAM_TIMEOUT`, `SERVICE_DEGRADED`, `INTERNAL_ERROR` | Machine-readable error codes (§7). |

**Consumer guidance:** treat all enums as **open** for forward compatibility — a client must tolerate an unrecognized value (e.g., a new `WeatherCondition`) without failing (§12, §15).

---

## 11. Validation Rules

| Rule | Specification | On violation |
|---|---|---|
| **Required fields** | `startDate`, `endDate` on intelligence/raw/narrative; `NarrativeRequest.startDate`/`endDate`. | `400 VALIDATION_ERROR` |
| **Optional fields** | `language` (narrative). Unknown query params ignored. | — |
| **Coordinate validation** | `locationId` parses to `lat,lon`; `lat ∈ [-90, 90]`, `lon ∈ [-180, 180]`. | `400` (or `404` if unresolvable) |
| **Date validation** | ISO-8601 `YYYY-MM-DD`; real calendar dates. | `400 VALIDATION_ERROR` |
| **Date range** | `startDate ≤ endDate`. | `400 VALIDATION_ERROR` |
| **Range length** | Span within the maximum forecast horizon: up to **16 days** and not more than 16 days ahead of the current date (configurable). | `400 VALIDATION_ERROR` |
| **Format validation** | Headers/body well-formed JSON; correct `Content-Type` on `POST`. | `400 VALIDATION_ERROR` |
| **Language** | `language`, if present, is a supported code (`en` in v1). | `400 VALIDATION_ERROR` |
| **Business validation** | Requested dates fall within the supported forecast window; historical-only ranges are not served by v1 forecast endpoints. | `400 VALIDATION_ERROR` |
| **Cross-field validation** | `endDate ≥ startDate`; range length rule above; `tempMaxC ≥ tempMinC` holds in all emitted data. | `400` for inputs |

Validation occurs at the API boundary before any provider call or computation.

---

## 12. API Versioning

| Aspect | Policy |
|---|---|
| **Version strategy** | Major version in the URI path (`/api/v1`). `metadata.apiVersion` reports the precise contract version (e.g., `1.0`). |
| **Backward compatibility** | Within a major version, only additive changes: new endpoints, new optional fields, new enum values. Consumers must ignore unknown fields and tolerate unknown enum values. |
| **Breaking changes** | Removing/renaming a field, changing a type, changing required-ness, or altering semantics requires a new major version (`/api/v2`). |
| **Deprecation policy** | Deprecated elements are documented and announced ahead of removal; a superseding major version runs in parallel during the transition. |
| **Migration strategy** | New major versions are introduced side-by-side; consumers migrate by changing the path prefix; no silent behavior changes within a version. |

---

## 13. Example Payload Library

**Successful Request** (§8.1):
```http
GET /api/v1/locations/15.2993,74.1240/intelligence?startDate=2026-08-01&endDate=2026-08-05
X-API-Key: sk_live_xxx
Accept: application/json
```

**Successful Response** (`200`):
```json
{
  "success": true,
  "data": {
    "location": { "id": "15.2993,74.1240", "name": "Goa", "latitude": 15.2993, "longitude": 74.1240 },
    "period": { "startDate": "2026-08-01", "endDate": "2026-08-05" },
    "dailyIntelligence": [
      {
        "date": "2026-08-01",
        "summary": {
          "tempMinC": 24, "tempMaxC": 31,
          "precipitationProbability": 0.7, "windSpeedKph": 18, "condition": "heavy_rain"
        },
        "riskAssessment": {
          "overallRiskLevel": "high",
          "riskFactors": [
            { "type": "rain", "severity": "high", "description": "70% chance of heavy rain", "rule": "precip_prob_gt_0_6" }
          ]
        },
        "activitySuitability": [
          { "activity": "outdoor_sightseeing", "score": 20 },
          { "activity": "indoor_museum", "score": 85 },
          { "activity": "beach", "score": 15 }
        ],
        "packingRecommendations": ["waterproof jacket", "quick-dry footwear"],
        "travelAdvisory": "avoid"
      }
    ],
    "tripSummary": {
      "bestDays": ["2026-08-04"],
      "worstDays": ["2026-08-01"],
      "overallPackingList": ["waterproof jacket", "light cottons", "sunscreen"],
      "overallRiskLevel": "moderate",
      "tripSuitabilityScore": 62,
      "travelConfidence": 0.78
    },
    "narrative": null
  },
  "metadata": {
    "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:00Z", "requestId": "req_9f2c1a7b",
    "cacheStatus": "hit", "ruleConfigVersion": "2026.07", "degraded": false
  },
  "error": null
}
```

**Validation Error** (`400`):
```json
{
  "success": false, "data": null,
  "metadata": { "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:00Z", "requestId": "req_3a7e22c9" },
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "endDate must be on or after startDate.",
    "details": [ { "field": "endDate", "issue": "endDate 2026-07-31 precedes startDate 2026-08-01" } ]
  }
}
```

**Authentication Error** (`401`):
```json
{
  "success": false, "data": null,
  "metadata": { "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:00Z", "requestId": "req_auth_77" },
  "error": { "code": "AUTHENTICATION_ERROR", "message": "Missing or invalid API key." }
}
```

**Provider Failure** (`503`) — all providers exhausted, no stored data:
```json
{
  "success": false, "data": null,
  "metadata": { "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:00Z", "requestId": "req_prov_12" },
  "error": { "code": "PROVIDER_UNAVAILABLE", "message": "Weather data is temporarily unavailable. Please retry later." }
}
```

**Daily Weather Intelligence** (single `DailyIntelligence` element): see the first entry of `dailyIntelligence` above.

**Trip Summary** (`TripSummary`): see `tripSummary` above.

**Packing Recommendation** (`PackingView`, §8.3):
```json
{
  "success": true,
  "data": {
    "location": { "id": "15.2993,74.1240", "name": "Goa", "latitude": 15.2993, "longitude": 74.1240 },
    "period": { "startDate": "2026-08-01", "endDate": "2026-08-05" },
    "overallPackingList": ["waterproof jacket", "light cottons", "sunscreen", "quick-dry footwear"]
  },
  "metadata": { "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:00Z", "requestId": "req_pack_04", "cacheStatus": "hit", "ruleConfigVersion": "2026.07", "degraded": false },
  "error": null
}
```

**Travel Advisory** (field within a day): `"travelAdvisory": "avoid"` (see the daily entry above).

**Weather Insights** (`BestDaysView`, §8.2):
```json
{
  "success": true,
  "data": {
    "location": { "id": "15.2993,74.1240", "name": "Goa", "latitude": 15.2993, "longitude": 74.1240 },
    "period": { "startDate": "2026-08-01", "endDate": "2026-08-05" },
    "bestDays": ["2026-08-04"],
    "worstDays": ["2026-08-01"],
    "overallRiskLevel": "moderate"
  },
  "metadata": { "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:00Z", "requestId": "req_best_08", "cacheStatus": "hit", "ruleConfigVersion": "2026.07", "degraded": false },
  "error": null
}
```

**AI Narration** (`POST` §8.5) — LLM success:
```json
{
  "success": true,
  "data": {
    "location": { "id": "15.2993,74.1240", "name": "Goa", "latitude": 15.2993, "longitude": 74.1240 },
    "period": { "startDate": "2026-08-01", "endDate": "2026-08-05" },
    "narrative": {
      "generatedByLLM": true,
      "summaryText": "Expect heavy rain at the start of your trip, especially Aug 1, which is best kept for indoor plans. Conditions ease toward Aug 4, your best day for the beach. Pack a waterproof jacket and light cottons.",
      "modelUsed": "provider/model-id",
      "fallbackUsed": false
    }
  },
  "metadata": { "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:05Z", "requestId": "req_narr_21", "cacheStatus": "miss", "ruleConfigVersion": "2026.07", "degraded": false },
  "error": null
}
```

**AI Narration** — fallback (AI disabled/failed; still `200`):
```json
{
  "success": true,
  "data": {
    "location": { "id": "15.2993,74.1240", "name": "Goa", "latitude": 15.2993, "longitude": 74.1240 },
    "period": { "startDate": "2026-08-01", "endDate": "2026-08-05" },
    "narrative": {
      "generatedByLLM": false,
      "summaryText": "Best day: Aug 4. Worst day: Aug 1 (heavy rain). Overall trip risk: moderate. Suggested packing: waterproof jacket, light cottons, sunscreen.",
      "modelUsed": null,
      "fallbackUsed": true
    }
  },
  "metadata": { "apiVersion": "1.0", "generatedAt": "2026-07-21T10:00:05Z", "requestId": "req_narr_22", "cacheStatus": "miss", "ruleConfigVersion": "2026.07", "degraded": false },
  "error": null
}
```

**Metadata** (envelope block): see any response above.

---

## 14. Data Lifecycle (conceptual)

High-level path of a request, from the consumer's perspective. This is a contract-level view, not an architecture description.

```
Client request (location + date range, API key)
   ->  REST API            : authenticate, validate, apply the response envelope
   ->  Weather Provider Layer (internal) : obtain data from an internal provider (or cache)
   ->  Normalization (internal)          : provider data mapped to one internal model
   ->  Weather Intelligence Processing   : deterministic risk / suitability / packing / best-worst
   ->  AI Narration (optional, separate call) : plain-language restatement, never alters values
   ->  Standardized JSON response (envelope: success / data / metadata / error)
```

Key contract facts implied by this flow:
1. The deterministic response (§8.1–8.4) is produced without the AI step; narration (§8.5) is a separate request.
2. Provider selection, caching, and normalization are invisible to the consumer; only the standardized payload is returned.
3. `metadata.cacheStatus` and `metadata.degraded` are the only signals a consumer receives about how the data was sourced — never a provider identity.

---

## 15. Consumer Integration Guidelines

| Topic | Recommendation |
|---|---|
| **Retries** | Retry only on `429`, `503`, `UPSTREAM_TIMEOUT`, and `INTERNAL_ERROR`, using exponential backoff with jitter. Never retry `400`/`401`/`403`/`404` unchanged. |
| **Caching** | Deterministic responses are cacheable client-side, keyed on `(locationId, startDate, endDate, ruleConfigVersion)`. Invalidate when `ruleConfigVersion` changes. Do not cache error responses. |
| **Timeouts** | Set a client timeout comfortably above typical deterministic latency. The narration endpoint (§8.5) is slower; allow a larger timeout for it specifically. |
| **Rate limits** | On `429`, honor the `Retry-After` header and back off. Batch and cache to stay within quota. |
| **Idempotency** | All `GET` endpoints are idempotent and safe to repeat. `POST /narrative` is not a data mutation; it may be retried, and identical inputs yield equivalent narration (subject to model/fallback state). |
| **Degraded handling** | Treat `success: true` with `metadata.degraded: true` (or `cacheStatus: "stale"`) as usable but possibly stale; consider a soft refresh later. |
| **Enum tolerance** | Tolerate unknown enum values (e.g., a new `WeatherCondition` or `ActivityCategory`) without failing — render a sensible default. |
| **Narration optionality** | Never make core UX depend on the AI narrative. Always render the deterministic data first; treat `narrative` as an enhancement, and handle `fallbackUsed: true` gracefully. |
| **Error recovery** | Surface `error.message` to users only when appropriate; log `error.code` and `metadata.requestId` for support. Use `requestId` when reporting an issue. |
| **Best practices** | Send `startDate`/`endDate` within the supported window; geocode place names client-side before calling; keep API keys server-side; depend only on documented fields. |

---

## 16. Appendix

### 16.1 Glossary
| Term | Definition |
|---|---|
| Weather Intelligence | Deterministic travel guidance derived from weather: risk, activity suitability, packing, timing (per-day + trip). |
| Deterministic response | Output identical for identical inputs and the same `ruleConfigVersion`. |
| Narration | Optional AI-generated natural-language restatement of intelligence; never alters computed values. |
| Fallback (narration) | Deterministic templated narrative returned when the AI layer is unavailable (`fallbackUsed: true`). |
| Degraded response | Valid data served in a reduced mode (e.g., stale or provider-fallback), flagged via `metadata.degraded`. |
| Provider independence | Guarantee that no weather-data response reveals which external provider supplied the data. |
| Rule config version | Identifier of the deterministic rule set behind computed values; drives cache invalidation. |
| Travel confidence | `0.0–1.0` indicator of how much to trust an assessment (forecast horizon, source agreement, data completeness). |
| locationId | Canonical location identifier; a `lat,lon` coordinate pair in v1. |

### 16.2 Abbreviations
| Abbr. | Meaning |
|---|---|
| API | Application Programming Interface |
| REST | Representational State Transfer |
| JSON | JavaScript Object Notation |
| LLM | Large Language Model |
| UTC | Coordinated Universal Time |
| ISO-8601 | International date/time format standard |
| TTL | Time To Live (cache) |
| BFF | Backend-For-Frontend |

### 16.3 References
| Document | Role |
|---|---|
| `01_Project_Bible.md` | Canonical source of truth (architecture, decisions). |
| `02_Product_Requirements_Document.md` | Product view (scope, requirements, personas). |
| `03_Technical_Design_Document.md` | Implementation view (components, data, testing). |
| This document | API & data contract (consumer-facing interface). |

### 16.4 Useful Notes
- This document governs the **public contract only**. Internal provider details (§4) are informational for maintainers and never leak into responses.
- All computed values are deterministic; only `narrative.summaryText` varies, and only via the separate narration endpoint.
- Forward compatibility depends on consumers ignoring unknown fields and tolerating unknown enum values.
- Units, coordinate format, and the `locationId` scheme are fixed for v1; changes to any of these would be a new major version.

---

*End of API & Data Contract Specification v1.0. This document defines the consumer-facing interface only; it does not modify or restate the Project Bible, PRD, or TRD, and the public API remains fully provider-independent.*
