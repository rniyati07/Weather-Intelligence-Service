"""`GetProviderHealth` — operational provider availability (API Spec §8.6).

The one use case permitted to surface provider identity, and only for the
maintainer endpoint. It reads the registry's cached, TTL-bounded snapshot
through the domain port, so it neither imports infrastructure nor generates
any upstream provider traffic.
"""

from app.domain.ports.provider_registry import ProviderHealthEntry, ProviderRegistryPort


class GetProviderHealth:
    """Reports the current health snapshot for every registered provider."""

    def __init__(self, *, registry: ProviderRegistryPort) -> None:
        self._registry = registry

    def execute(self) -> list[ProviderHealthEntry]:
        return self._registry.health_snapshot()
