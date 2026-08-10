from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    RoleBundle,
    SuiteMembership,
    SuiteRoleAssignment,
    SupportAccessGrant,
    Tenant,
    TenantEntitlement,
    TenantInvitation,
)
from app.models import User


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            TenantEntitlement.__table__,
            TenantInvitation.__table__,
            SuiteMembership.__table__,
            SuiteRoleAssignment.__table__,
            ProductInstallation.__table__,
            SupportAccessGrant.__table__,
            User.__table__,
        ],
    )
    return Session(engine)


def test_entitlement_is_unique_per_tenant_product() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.flush()
        session.add(
            TenantEntitlement(
                tenant_id=tenant.id,
                product_code=ProductCode.COMMIT_ARC,
                status="ACTIVE",
            )
        )
        session.commit()
        session.add(
            TenantEntitlement(
                tenant_id=tenant.id,
                product_code=ProductCode.COMMIT_ARC,
                status="ACTIVE",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_invitation_stores_digest_not_raw_token() -> None:
    invitation = TenantInvitation(
        tenant_id=uuid.uuid4(),
        email="owner@example.test",
        token_digest="a" * 64,
    )
    assert invitation.token_digest == "a" * 64
    assert not hasattr(invitation, "token")


def test_suite_membership_supports_role_assignments_and_installations() -> None:
    user_id = uuid.uuid4()
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.flush()
        membership = SuiteMembership(tenant_id=tenant.id, user_id=user_id)
        session.add(membership)
        session.flush()
        session.add(SuiteRoleAssignment(membership_id=membership.id, role_bundle=RoleBundle.EMPLOYEE))
        session.add(
            ProductInstallation(
                tenant_id=tenant.id,
                product_code=ProductCode.COMMIT_ARC,
                local_identifier="org-ara",
            )
        )
        session.add(
            SupportAccessGrant(
                tenant_id=tenant.id,
                operator_user_id=user_id,
                capabilities=["contacts.read"],
                reason="incident",
                expires_at=tenant.created_at,
            )
        )
        session.commit()
        assert membership.id
