from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TenantManifest:
    key: str
    legal_name: str
    display_name: str
    region: str
    locale: str
    timezone: str
    currency: str
    products: tuple[str, ...]
    owner_email: str
    allowed_email_domains: tuple[str, ...]
    admin_role_bundles: tuple[str, ...]
    secret_refs: tuple[str, ...]
    consent_policy: str
    branding_mode: str


_MANIFESTS = {
    "ara-global": TenantManifest(
        key="ara-global", legal_name="ARA Global", display_name="ARA Global",
        region="IN", locale="en-IN", timezone="Asia/Kolkata", currency="INR",
        products=("commitarc", "revenueos", "signalloop"), owner_email="owner@ara-global.test",
        allowed_email_domains=("ara-global.test",),
        admin_role_bundles=("TENANT_OWNER", "REVENUE_OS_ADMIN", "COMMIT_ARC_ADMIN", "ENGAGEMENT_ADMIN"),
        secret_refs=("oidc.ara-global.client", "branding.ara-global.asset"),
        consent_policy="knowledge-base", branding_mode="tenant",
    ),
    "ai-consulting": TenantManifest(
        key="ai-consulting", legal_name="AI Consulting Inc", display_name="AI Consulting",
        region="US", locale="en-US", timezone="America/New_York", currency="USD",
        products=("commitarc", "revenueos", "signalloop"), owner_email="owner@ai-consulting.test",
        allowed_email_domains=("ai-consulting.test",),
        admin_role_bundles=("TENANT_OWNER", "REVENUE_OS_ADMIN", "COMMIT_ARC_ADMIN", "ENGAGEMENT_ADMIN"),
        secret_refs=("oidc.ai-consulting.client", "branding.ai-consulting.asset"),
        consent_policy="us-consent-required", branding_mode="neutral",
    ),
}


def load_phase1_manifests(_directory: Path | None = None) -> dict[str, TenantManifest]:
    """Return the immutable, secret-free launch manifest set."""
    return dict(_MANIFESTS)
