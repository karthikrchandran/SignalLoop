from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.domain.branding.host_resolver import TrustedTenantHostResolver

router = APIRouter(prefix="/public", tags=["public-branding"])


def _resolver() -> TrustedTenantHostResolver:
    hosts = {
        pair.split("=", 1)[0].strip(): pair.split("=", 1)[1].strip()
        for pair in settings.TENANT_PUBLIC_HOSTS.split(",")
        if "=" in pair
    }
    return TrustedTenantHostResolver(
        hosts,
        environment=settings.ENVIRONMENT,
        trusted_proxies=set(settings.TRUSTED_PROXY_CIDRS.split(",")) - {""},
    )


def verified_tenant_host(request: Request) -> str | None:
    resolver = _resolver()
    peer = request.client.host if request.client else ""
    verified = request.headers.get("X-Verified-Tenant-Host")
    if settings.ENVIRONMENT == "local":
        return resolver.resolve(request.headers.get("host", ""))
    if not verified:
        return None
    return resolver.resolve_verified(verified, peer=peer)


@router.get("/entry")
def public_entry(
    tenant_key: str | None = Depends(verified_tenant_host),
) -> dict[str, object]:
    if not tenant_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace is not available"
        )
    entries = {
        "ara-global": {
            "display_name": "ARA Global Revenue Workspace",
            "headline": "Turn every customer commitment into coordinated action.",
            "primary_color": "#0f172a",
            "secondary_color": "#ffffff",
            "oidc_start_url": "/api/v1/oidc/start",
        },
        "ai-consulting": {
            "display_name": "AI Consulting Revenue Workspace",
            "headline": "Coordinate growth with one trusted workspace.",
            "primary_color": "#1e3a8a",
            "secondary_color": "#ffffff",
            "oidc_start_url": "/api/v1/oidc/start",
        },
    }
    entry = entries.get(tenant_key)
    if entry is None:
        raise HTTPException(status_code=404, detail="Workspace is not available")
    return {"tenant_key": tenant_key, **entry}
