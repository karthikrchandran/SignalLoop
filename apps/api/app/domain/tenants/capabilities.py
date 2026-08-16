"""Live suite capability resolution from tenant-local control-plane records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlmodel import Session, select

from app.domain.tenants.models import (
    ProductCode,
    RoleBundle,
    SuiteMembership,
    SuiteRoleAssignment,
    Tenant,
    TenantEntitlement,
)

_ROLE_CAPABILITIES: dict[RoleBundle, frozenset[str]] = {
    RoleBundle.EMPLOYEE: frozenset({"revenueos.essentials.read"}),
    RoleBundle.MANAGER: frozenset(
        {"revenueos.essentials.read", "revenueos.pipeline.read"}
    ),
    RoleBundle.ENGAGEMENT_OPERATOR: frozenset(
        {"revenueos.essentials.read", "signalloop.campaign.manage"}
    ),
    RoleBundle.TENANT_OWNER: frozenset(
        {
            "agents.admin.manage",
            "revenueos.essentials.read",
            "tenant.members.manage",
            "tenant.settings.manage",
        }
    ),
    RoleBundle.REVENUE_OS_ADMIN: frozenset(
        {"revenueos.essentials.read", "revenueos.admin.manage"}
    ),
    RoleBundle.COMMIT_ARC_ADMIN: frozenset(
        {"revenueos.essentials.read", "commitarc.admin.manage"}
    ),
    RoleBundle.ENGAGEMENT_ADMIN: frozenset(
        {
            "agents.admin.manage",
            "revenueos.essentials.read",
            "signalloop.admin.manage",
            "signalloop.campaign.manage",
        }
    ),
}


@dataclass(frozen=True)
class SuiteContext:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    products: frozenset[str]
    role_bundles: frozenset[RoleBundle]
    capabilities: frozenset[str]


def has_capability(bundle: RoleBundle | str, capability: str) -> bool:
    """Check the immutable role-to-capability registry."""
    try:
        role = bundle if isinstance(bundle, RoleBundle) else RoleBundle(bundle)
    except ValueError:
        return False
    return capability in _ROLE_CAPABILITIES.get(role, frozenset())


def resolve_suite_context(
    session: Session, *, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> SuiteContext:
    """Resolve active tenant, memberships, entitlements, and role capabilities."""
    tenant = session.get(Tenant, tenant_id)
    if tenant is None or tenant.status != "ACTIVE":
        raise PermissionError("tenant is not active")
    membership = session.exec(
        select(SuiteMembership).where(
            SuiteMembership.tenant_id == tenant_id,
            SuiteMembership.user_id == user_id,
            SuiteMembership.status == "ACTIVE",
        )
    ).one_or_none()
    if membership is None:
        raise PermissionError("membership is not active")
    entitlements = session.exec(
        select(TenantEntitlement).where(
            TenantEntitlement.tenant_id == tenant_id,
            TenantEntitlement.status == "ACTIVE",
        )
    ).all()
    if not entitlements:
        raise PermissionError("tenant entitlement is not active")
    roles = session.exec(
        select(SuiteRoleAssignment).where(
            SuiteRoleAssignment.membership_id == membership.id,
            SuiteRoleAssignment.status == "ACTIVE",
        )
    ).all()
    role_bundles = frozenset(RoleBundle(role.role_bundle) for role in roles)
    capabilities = frozenset(
        cap
        for bundle in role_bundles
        for cap in _ROLE_CAPABILITIES.get(bundle, frozenset())
    )
    products = frozenset(
        _product_code_value(entitlement.product_code) for entitlement in entitlements
    )
    return SuiteContext(user_id, tenant_id, products, role_bundles, capabilities)


def _product_code_value(product_code: ProductCode | str) -> str:
    if isinstance(product_code, ProductCode):
        return product_code.value
    return ProductCode(product_code).value
