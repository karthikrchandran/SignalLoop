from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


class ProviderEgressError(RuntimeError):
    """Raised when an acceptance fake would contact a non-loopback host."""


@dataclass
class FakeProviderHub:
    calls: list[str] = field(default_factory=list)

    def request(self, url: str, *, operation: str = "request") -> dict[str, str]:
        parsed = urlparse(url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ProviderEgressError(f"external provider egress blocked: {parsed.hostname}")
        self.calls.append(f"{operation}:{url}")
        return {"status": "accepted", "provider": "fake"}

    def provision_tenant(self, tenant_key: str) -> str:
        marker = f"tenant:{tenant_key}"
        if marker not in self.calls:
            self.calls.append(marker)
        return "CREATED" if self.calls.count(marker) == 1 else "UNCHANGED"
