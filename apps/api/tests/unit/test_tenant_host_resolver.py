from app.domain.branding.host_resolver import TrustedTenantHostResolver


def test_resolves_allowlisted_local_aliases() -> None:
    resolver = TrustedTenantHostResolver(
        {"ara.localhost": "ara-global", "ai-consulting.localhost": "ai-consulting"},
        environment="local",
    )
    assert resolver.resolve("ara.localhost") == "ara-global"


def test_rejects_unknown_hosts_and_query_authority() -> None:
    resolver = TrustedTenantHostResolver(
        {"ara.example.test": "ara-global"},
        environment="production",
        trusted_proxies={"10.0.0.1"},
    )
    assert resolver.resolve("unknown.example.test") is None
    assert resolver.resolve("ara.example.test?tenant=ai-consulting") is None
    assert resolver.resolve_verified("ara.example.test", peer="192.0.2.1") is None


def test_only_trusted_proxy_verified_header_is_authoritative() -> None:
    resolver = TrustedTenantHostResolver(
        {"ara.example.test": "ara-global"},
        environment="production",
        trusted_proxies={"10.0.0.1"},
    )
    assert (
        resolver.resolve_verified("ara.example.test", peer="10.0.0.1") == "ara-global"
    )
