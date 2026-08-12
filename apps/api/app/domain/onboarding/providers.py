from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


class ProviderEgressError(RuntimeError):
    """Raised when an acceptance fake would contact a non-loopback host."""


class ProviderOutcomeUnknownError(RuntimeError):
    """The provider may have accepted the request before the caller crashed."""


@dataclass
class FakeProviderHub:
    calls: list[str] = field(default_factory=list)
    accepted_then_crash_for: set[str] = field(default_factory=set)

    def request(self, url: str, *, operation: str = "request") -> dict[str, str]:
        parsed = urlparse(url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ProviderEgressError(f"external provider egress blocked: {parsed.hostname}")
        self.calls.append(f"{operation}:{url}")
        return {"status": "accepted", "provider": "fake"}

    def provision_tenant(self, tenant_key: str) -> str:
        marker = f"tenant:{tenant_key}"
        self.calls.append(marker)
        if tenant_key in self.accepted_then_crash_for:
            self.accepted_then_crash_for.remove(tenant_key)
            raise ProviderOutcomeUnknownError(f"accepted then crashed for {tenant_key}")
        return "CREATED" if self.calls.count(marker) == 1 else "UNCHANGED"
