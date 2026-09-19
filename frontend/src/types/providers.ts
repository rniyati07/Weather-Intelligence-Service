/**
 * Provider health — API Spec §9.11. **Operator-facing only.**
 *
 * This is the one payload in the contract that carries provider identity.
 * A provider name must never render on a consumer-facing screen (FDS §6.5),
 * and the endpoint requires an operator key — a consumer key gets `403`.
 */

import type { IsoDateTime } from './common'
import type { ProviderStatus } from './enums'

export interface ProviderHealth {
  /** Internal provider name. Operator screens only. */
  provider: string
  status: ProviderStatus
  lastCheckedAt: IsoDateTime
}

/** Payload of `GET /providers/health` — API Spec §8.6. */
export interface ProviderHealthView {
  providers: ProviderHealth[]
}
