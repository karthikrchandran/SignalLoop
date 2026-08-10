from __future__ import annotations

from urllib.parse import urlsplit


class TrustedTenantHostResolver:
    """Resolve public tenant keys from deployment-controlled host authority."""

    def __init__(
        self,
        hosts: dict[str, str],
        *,
        environment: str = "production",
        trusted_proxies: set[str] | None = None,
    ) -> None:
        self.hosts = {self._canonical(host): key for host, key in hosts.items()}
        self.environment = environment
        self.trusted_proxies = trusted_proxies or set()

    def resolve(self, host: str) -> str | None:
        if self.environment != "local":
            return None
        return self.hosts.get(self._canonical(host))

    def resolve_verified(self, verified_host: str, *, peer: str) -> str | None:
        if peer not in self.trusted_proxies:
            return None
        return self.hosts.get(self._canonical(verified_host))

    @staticmethod
    def _canonical(host: str) -> str:
        parsed = urlsplit(host if "://" in host else f"//{host}")
        if parsed.query or parsed.path not in ("", "/"):
            return ""
        return (parsed.hostname or "").rstrip(".").lower()
