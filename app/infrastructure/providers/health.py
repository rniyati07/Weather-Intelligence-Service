"""Passive, TTL-bounded provider health tracking.

Health is updated from real call outcomes as the registry fetches — this
module never itself makes a network call. A single failure marks a provider
`DEGRADED` (still selectable: it might have been transient); consecutive
failures escalate it to `UNAVAILABLE` (skipped by `select()`, guide §5.3).
A cached entry older than `PROVIDER_HEALTH_TTL_SECONDS` is treated as
`AVAILABLE` again rather than stuck in a stale state forever.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

_CONSECUTIVE_FAILURES_UNTIL_UNAVAILABLE = 2


class ProviderStatus(StrEnum):
    """Operational provider state (API Spec §10 `ProviderStatus`)."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    #: Never actually called — distinct from `AVAILABLE`, which now means
    #: "no *recorded failure*" only once at least one call has happened.
    #: Additive per the contract's own versioning policy (API Spec §12:
    #: "new enum values" are backward-compatible; consumers must already
    #: "tolerate unknown enum values" per §15.2). See ISSUE-3 in the E2E
    #: audit: reporting an unprobed provider as `available` let an operator
    #: read three never-called fallback providers as "verified reachable"
    #: when only the primary had ever actually been exercised.
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HealthRecord:
    status: ProviderStatus
    checked_at: datetime


class HealthTracker:
    """In-memory, per-provider health cache with TTL-bounded freshness."""

    def __init__(self, *, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._records: dict[str, HealthRecord] = {}
        self._consecutive_failures: dict[str, int] = {}

    def record_success(self, provider_name: str) -> None:
        self._consecutive_failures[provider_name] = 0
        self._set(provider_name, ProviderStatus.AVAILABLE)

    def record_failure(self, provider_name: str) -> None:
        failures = self._consecutive_failures.get(provider_name, 0) + 1
        self._consecutive_failures[provider_name] = failures
        status = (
            ProviderStatus.UNAVAILABLE
            if failures >= _CONSECUTIVE_FAILURES_UNTIL_UNAVAILABLE
            else ProviderStatus.DEGRADED
        )
        self._set(provider_name, status)

    def status(self, provider_name: str) -> ProviderStatus:
        """Cached status, TTL-bounded.

        No record at all means this provider has never actually been called
        — reported as `UNKNOWN`, not `AVAILABLE`. An *expired* record is a
        different case: it was genuinely exercised at some point with no
        failure since, so it reads as `AVAILABLE` again rather than staying
        stuck in a stale state forever.
        """
        record = self._records.get(provider_name)
        if record is None:
            return ProviderStatus.UNKNOWN
        age_seconds = (datetime.now(UTC) - record.checked_at).total_seconds()
        if age_seconds > self._ttl_seconds:
            return ProviderStatus.AVAILABLE
        return record.status

    def snapshot(self) -> dict[str, HealthRecord]:
        """All currently tracked records — feeds the on-demand `/providers/health` probe."""
        return dict(self._records)

    def _set(self, provider_name: str, status: ProviderStatus) -> None:
        self._records[provider_name] = HealthRecord(status=status, checked_at=datetime.now(UTC))
