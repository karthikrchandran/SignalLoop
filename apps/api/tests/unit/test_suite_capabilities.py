from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.tenants.capabilities import has_capability, resolve_suite_context
from app.domain.tenants.models import (
    RoleBundle,
    SuiteMembership,
    SuiteRoleAssignment,
    Tenant,
    TenantEntitlement,
)
from app.models import User


@pytest.mark.parametrize(
    ("bundle", "capability", "allowed"),
    [
        (RoleBundle.EMPLOYEE, "revenueos.essentials.read", True),
        (RoleBundle.EMPLOYEE, "signalloop.campaign.manage", False),
        (RoleBundle.ENGAGEMENT_OPERATOR, "signalloop.campaign.manage", True),
        (RoleBundle.TENANT_OWNER, "tenant.members.manage", True),
    ],
)
def test_role_bundle_capabilities(bundle: RoleBundle, capability: str, allowed: bool) -> None:
    assert has_capability(bundle, capability) is allowed


def test_resolve_suite_context_requires_active_entitlement() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            TenantEntitlement.__table__,
            SuiteMembership.__table__,
            SuiteRoleAssignment.__table__,
            User.__table__,
        ],
    )
    user_id = uuid.uuid4()
    with Session(engine) as session:
        tenant = Tenant(key="ara", display_name="ARA")
        session.add(tenant)
        session.flush()
        membership = SuiteMembership(tenant_id=tenant.id, user_id=user_id)
        session.add(membership)
        session.flush()
        session.add(SuiteRoleAssignment(membership_id=membership.id, role_bundle=RoleBundle.EMPLOYEE))
        session.commit()
        with pytest.raises(PermissionError, match="entitlement"):
            resolve_suite_context(session, user_id=user_id, tenant_id=tenant.id)
