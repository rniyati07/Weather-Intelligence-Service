"""Unit tests for the passive, TTL-bounded provider health tracker. Offline, no network."""

import time

from app.infrastructure.providers.health import HealthTracker, ProviderStatus


class TestPassiveUpdates:
    def test_unknown_provider_defaults_to_available(self) -> None:
        tracker = HealthTracker(ttl_seconds=60)
        assert tracker.status("open_meteo") == ProviderStatus.AVAILABLE

    def test_success_marks_available(self) -> None:
        tracker = HealthTracker(ttl_seconds=60)
        tracker.record_failure("openweather")
        tracker.record_success("openweather")
        assert tracker.status("openweather") == ProviderStatus.AVAILABLE

    def test_single_failure_marks_degraded_not_unavailable(self) -> None:
        tracker = HealthTracker(ttl_seconds=60)
        tracker.record_failure("openweather")
        assert tracker.status("openweather") == ProviderStatus.DEGRADED

    def test_consecutive_failures_escalate_to_unavailable(self) -> None:
        tracker = HealthTracker(ttl_seconds=60)
        tracker.record_failure("openweather")
        tracker.record_failure("openweather")
        assert tracker.status("openweather") == ProviderStatus.UNAVAILABLE

    def test_success_resets_consecutive_failure_count(self) -> None:
        tracker = HealthTracker(ttl_seconds=60)
        tracker.record_failure("openweather")
        tracker.record_success("openweather")
        tracker.record_failure("openweather")
        # Only one failure since the last success -> degraded, not unavailable.
        assert tracker.status("openweather") == ProviderStatus.DEGRADED


class TestTtlExpiry:
    def test_expired_unavailable_record_reads_as_available(self) -> None:
        tracker = HealthTracker(ttl_seconds=0.05)
        tracker.record_failure("openweather")
        tracker.record_failure("openweather")
        assert tracker.status("openweather") == ProviderStatus.UNAVAILABLE
        time.sleep(0.1)  # elapsed time now exceeds the TTL
        assert tracker.status("openweather") == ProviderStatus.AVAILABLE

    def test_fresh_record_within_ttl_is_respected(self) -> None:
        tracker = HealthTracker(ttl_seconds=60)
        tracker.record_failure("openweather")
        tracker.record_failure("openweather")
        assert tracker.status("openweather") == ProviderStatus.UNAVAILABLE


class TestSnapshot:
    def test_snapshot_reflects_all_tracked_providers(self) -> None:
        tracker = HealthTracker(ttl_seconds=60)
        tracker.record_success("open_meteo")
        tracker.record_failure("openweather")

        snapshot = tracker.snapshot()

        assert snapshot["open_meteo"].status == ProviderStatus.AVAILABLE
        assert snapshot["openweather"].status == ProviderStatus.DEGRADED
