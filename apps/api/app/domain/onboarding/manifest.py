from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

_SUPPORTED_PRODUCTS = frozenset({"commitarc", "revenueos", "signalloop"})
_REGION_PROFILES = {"IN": ("en-IN", "INR"), "US": ("en-US", "USD")}
_SUPPORTED_CHANNELS = frozenset({"email", "sms", "voice", "chat"})
_COMPLIANCE_PACKS = frozenset({"india-dpdp", "knowledge-release", "us-consent"})
_SECRET_REFERENCE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
_LOCALE = re.compile(r"^[a-z]{2,3}-[A-Z]{2}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


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
    schema_version: str = "phase1.v1"
    product_editions: dict[str, str] = field(default_factory=dict)
    compliance_packs: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()


_MANIFESTS = {
    "ara-global": TenantManifest(
        key="ara-global", legal_name="ARA Global", display_name="ARA Global",
        region="IN", locale="en-IN", timezone="Asia/Kolkata", currency="INR",
        products=("commitarc", "revenueos", "signalloop"), owner_email="owner@ara-global.test",
        allowed_email_domains=("ara-global.test",),
        admin_role_bundles=("TENANT_OWNER", "REVENUE_OS_ADMIN", "COMMIT_ARC_ADMIN", "ENGAGEMENT_ADMIN"),
        secret_refs=("oidc.ara-global.client", "branding.ara-global.asset"),
        consent_policy="knowledge-base", branding_mode="tenant",
        product_editions={"commitarc": "enterprise", "revenueos": "enterprise", "signalloop": "enterprise"},
        compliance_packs=("india-dpdp", "knowledge-release"),
        channels=("email", "sms", "voice", "chat"),
    ),
    "ai-consulting": TenantManifest(
        key="ai-consulting", legal_name="AI Consulting Inc", display_name="AI Consulting",
        region="US", locale="en-US", timezone="America/New_York", currency="USD",
        products=("commitarc", "revenueos", "signalloop"), owner_email="owner@ai-consulting.test",
        allowed_email_domains=("ai-consulting.test",),
        admin_role_bundles=("TENANT_OWNER", "REVENUE_OS_ADMIN", "COMMIT_ARC_ADMIN", "ENGAGEMENT_ADMIN"),
        secret_refs=("oidc.ai-consulting.client", "branding.ai-consulting.asset"),
        consent_policy="us-consent-required", branding_mode="neutral",
        product_editions={"commitarc": "enterprise", "revenueos": "enterprise", "signalloop": "enterprise"},
        compliance_packs=("us-consent", "knowledge-release"),
        channels=("email", "sms", "voice", "chat"),
    ),
}


def validate_manifest(manifest: TenantManifest) -> None:
    """Reject incomplete tenant definitions and values that could be secrets."""
    if manifest.schema_version != "phase1.v1":
        raise ValueError("unsupported manifest schema version")
    if not manifest.products or not set(manifest.products).issubset(_SUPPORTED_PRODUCTS):
        raise ValueError("unsupported product in manifest")
    if set(manifest.product_editions) != set(manifest.products) or not all(manifest.product_editions.values()):
        raise ValueError("each product requires an edition")
    if manifest.region not in _REGION_PROFILES or _REGION_PROFILES[manifest.region] != (manifest.locale, manifest.currency):
        raise ValueError("unsupported region, locale, or currency combination")
    if not _LOCALE.fullmatch(manifest.locale) or not _CURRENCY.fullmatch(manifest.currency):
        raise ValueError("invalid locale or currency")
    if not manifest.compliance_packs or not set(manifest.compliance_packs).issubset(_COMPLIANCE_PACKS):
        raise ValueError("unsupported compliance pack")
    if not manifest.channels or not set(manifest.channels).issubset(_SUPPORTED_CHANNELS):
        raise ValueError("unsupported channel")
    try:
        ZoneInfo(manifest.timezone)
    except Exception as exc:
        raise ValueError("invalid timezone") from exc
    if not all(_SECRET_REFERENCE.fullmatch(reference) for reference in manifest.secret_refs):
        raise ValueError("inline secret or invalid secret reference")


def load_phase1_manifests(_directory: Path | None = None) -> dict[str, TenantManifest]:
    """Return the immutable, secret-free launch manifest set."""
    for manifest in _MANIFESTS.values():
        validate_manifest(manifest)
    return dict(_MANIFESTS)
