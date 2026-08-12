from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes.onboarding import (
    OnboardingReconciliation,
    _authorize_run_tenant,
    reconcile_run_stage,
)
from app.domain.audit.audit_events import AuditEvent
from app.domain.onboarding.persistence import OnboardingRunRecord, OnboardingStageRecord
from app.domain.onboarding.persistence_service import create_or_resume
from app.domain.onboarding.providers import FakeProviderHub
from app.domain.tenants.capabilities import SuiteContext
from app.domain.tenants.models import Tenant
from app.models import SQLModel as _ModelsLoaded  # noqa: F401


def _unknown_run(session: Session) -> tuple[OnboardingRunRecord, OnboardingStageRecord]:
    run = create_or_resume(session, "ara-global", "reconciliation-route", providers=FakeProviderHub(accepted_then_crash_for={"ara-global"}))
    stage = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id)).first()
    assert stage is not None
    return run, stage


def test_reconciliation_payload_requires_provider_receipt() -> None:
    with pytest.raises(ValueError):
        OnboardingReconciliation(decision="NOT_ACCEPTED", provider_receipt_id="")


def test_cross_tenant_operator_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        user = type("User", (), {"id": uuid.uuid4(), "is_superuser": False})()
        monkeypatch.setattr(
            "app.api.routes.onboarding.resolve_suite_context",
            lambda *_args, **_kwargs: SuiteContext(user.id, uuid.uuid4(), frozenset(), frozenset(), frozenset({"revenueos.admin.manage"})),
        )
        with pytest.raises(HTTPException) as error:
            _authorize_run_tenant(session, user, "ara-global")
        assert error.value.status_code == 403


def test_unauthorized_operator_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.commit()
        user = type("User", (), {"id": uuid.uuid4(), "is_superuser": False})()
        monkeypatch.setattr(
            "app.api.routes.onboarding.resolve_suite_context",
            lambda *_args, **_kwargs: SuiteContext(user.id, tenant.id, frozenset(), frozenset(), frozenset()),
        )
        with pytest.raises(HTTPException) as error:
            _authorize_run_tenant(session, user, "ara-global")
        assert error.value.status_code == 403


def test_operator_reconciliation_is_audited_and_unblocks_stage() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Tenant(key="ara-global", display_name="ARA Global"))
        session.commit()
        run, stage = _unknown_run(session)
        user = type("User", (), {"id": uuid.uuid4(), "is_superuser": True, "role": "admin"})()
        result = reconcile_run_stage(
            session=session,
            current_user=user,
            run_id=run.id,
            stage_id=stage.id,
            body=OnboardingReconciliation(decision="OPERATOR_APPROVED_SAFE_RETRY", provider_receipt_id="receipt-123"),
            idempotency_key="reconcile-123",
        )
        assert result["status"] == "FAILED"
        assert result["stages"][0]["status"] == "PENDING"
        audit = session.exec(select(AuditEvent).where(AuditEvent.event_name == "onboarding.external_outcome.reconciled")).one()
        assert audit.actor_id == user.id
        assert audit.payload["provider_receipt_id"] == "receipt-123"


def test_endpoint_requires_idempotency_key() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Tenant(key="ara-global", display_name="ARA Global"))
        session.commit()
        run, stage = _unknown_run(session)
        user = type("User", (), {"id": uuid.uuid4(), "is_superuser": True, "role": "admin"})()
        with pytest.raises(HTTPException) as error:
            reconcile_run_stage(
                session=session,
                current_user=user,
                run_id=run.id,
                stage_id=stage.id,
                body=OnboardingReconciliation(decision="NOT_ACCEPTED", provider_receipt_id="receipt-1"),
                idempotency_key=None,
            )
        assert error.value.status_code == 400
