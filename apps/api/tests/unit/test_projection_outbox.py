from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.projections.outbox import ProjectionConflict, enqueue_projection
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    SuiteProjectionOutbox,
    Tenant,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[Tenant.__table__, ProductInstallation.__table__, SuiteProjectionOutbox.__table__],
    )
    return Session(engine)


def test_enqueue_projection_is_idempotent_for_matching_payload() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.flush()
        installation = ProductInstallation(
            tenant_id=tenant.id,
            product_code=ProductCode.REVENUE_OS,
            local_identifier="org-ara",
        )
        session.add(installation)
        session.flush()

        first = enqueue_projection(
            session,
            tenant_id=tenant.id,
            installation_id=installation.id,
            projection_kind="tenant_membership",
            projection_version=4,
            payload={"roles": ["EMPLOYEE"], "user_id": "user-123"},
        )
        second = enqueue_projection(
            session,
            tenant_id=tenant.id,
            installation_id=installation.id,
            projection_kind="tenant_membership",
            projection_version=4,
            payload={"user_id": "user-123", "roles": ["EMPLOYEE"]},
        )

        assert first.id == second.id
        assert first.status == "PENDING"
        assert first.attempt_count == 0
        assert len(first.payload_digest) == 64


def test_enqueue_projection_rejects_conflicting_payload_for_same_version() -> None:
    with _session() as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.flush()
        installation = ProductInstallation(
            tenant_id=tenant.id,
            product_code=ProductCode.REVENUE_OS,
            local_identifier="org-ara",
        )
        session.add(installation)
        session.flush()

        enqueue_projection(
            session,
            tenant_id=tenant.id,
            installation_id=installation.id,
            projection_kind="tenant_membership",
            projection_version=4,
            payload={"roles": ["EMPLOYEE"], "user_id": "user-123"},
        )

        with pytest.raises(ProjectionConflict, match="already has a different payload"):
            enqueue_projection(
                session,
                tenant_id=tenant.id,
                installation_id=installation.id,
                projection_kind="tenant_membership",
                projection_version=4,
                payload={"roles": ["TENANT_OWNER"], "user_id": "user-123"},
            )
