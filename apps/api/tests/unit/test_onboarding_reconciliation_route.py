from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.requests import Request

from app.api.routes.onboarding import (
    OnboardingReconciliation,
    _authorize_run_tenant,
    reconcile_run_stage,
)
from app.domain.audit.audit_events import AuditEvent
from app.domain.onboarding.persistence import (
    OnboardingEvidenceRecord,
    OnboardingRunRecord,
    OnboardingStageRecord,
)
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


def _request(run_id: uuid.UUID, stage_id: uuid.UUID) -> Request:
    return Request({"type": "http", "method": "POST", "path": f"/api/v1/onboarding/runs/{run_id}/stages/{stage_id}/reconcile", "headers": [], "scheme": "http", "server": ("testserver", 80), "query_string": b""})


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
        result = asyncio.run(reconcile_run_stage(
            request=_request(run.id, stage.id),
            session=session,
            current_user=user,
            run_id=run.id,
            stage_id=stage.id,
            body=OnboardingReconciliation(decision="OPERATOR_APPROVED_SAFE_RETRY", provider_receipt_id="receipt-123"),
            idempotency_key="reconcile-123",
        ))
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
            asyncio.run(reconcile_run_stage(
                request=_request(run.id, stage.id),
                session=session,
                current_user=user,
                run_id=run.id,
                stage_id=stage.id,
                body=OnboardingReconciliation(decision="NOT_ACCEPTED", provider_receipt_id="receipt-1"),
                idempotency_key=None,
            ))
        assert error.value.status_code == 400


def test_same_reconciliation_key_replays_without_duplicate_audit() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Tenant(key="ara-global", display_name="ARA Global"))
        session.commit()
        run, stage = _unknown_run(session)
        user = type("User", (), {"id": uuid.uuid4(), "is_superuser": True, "role": "admin"})()
        request = _request(run.id, stage.id)
        body = OnboardingReconciliation(decision="NOT_ACCEPTED", provider_receipt_id="receipt-replay")
        first = asyncio.run(reconcile_run_stage(request=request, session=session, current_user=user, run_id=run.id, stage_id=stage.id, body=body, idempotency_key="replay-key"))
        second = asyncio.run(reconcile_run_stage(request=request, session=session, current_user=user, run_id=run.id, stage_id=stage.id, body=body, idempotency_key="replay-key"))
        assert first == second
        assert len(session.exec(select(AuditEvent).where(AuditEvent.event_name == "onboarding.external_outcome.reconciled")).all()) == 1


def test_same_key_with_changed_receipt_is_rejected() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Tenant(key="ara-global", display_name="ARA Global"))
        session.commit()
        run, stage = _unknown_run(session)
        user = type("User", (), {"id": uuid.uuid4(), "is_superuser": True, "role": "admin"})()
        request = _request(run.id, stage.id)
        asyncio.run(reconcile_run_stage(request=request, session=session, current_user=user, run_id=run.id, stage_id=stage.id, body=OnboardingReconciliation(decision="NOT_ACCEPTED", provider_receipt_id="receipt-one"), idempotency_key="conflict-key"))
        with pytest.raises(HTTPException) as error:
            asyncio.run(reconcile_run_stage(request=request, session=session, current_user=user, run_id=run.id, stage_id=stage.id, body=OnboardingReconciliation(decision="OPERATOR_APPROVED_SAFE_RETRY", provider_receipt_id="receipt-two"), idempotency_key="conflict-key"))
        assert error.value.status_code == 409


def test_concurrent_reconciliation_key_has_one_audit_and_one_evidence_side_effect(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'reconcile-race.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Tenant(key="ara-global", display_name="ARA Global"))
        session.commit()
        run, stage = _unknown_run(session)
        run_id, stage_id = run.id, stage.id
    user = type("User", (), {"id": uuid.uuid4(), "is_superuser": True, "role": "admin"})()

    def reconcile() -> dict[str, object]:
        with Session(engine) as session:
            run = session.get(OnboardingRunRecord, run_id)
            stage = session.get(OnboardingStageRecord, stage_id)
            assert run and stage
            return asyncio.run(reconcile_run_stage(request=_request(run_id, stage_id), session=session, current_user=user, run_id=run_id, stage_id=stage_id, body=OnboardingReconciliation(decision="NOT_ACCEPTED", provider_receipt_id="receipt-race"), idempotency_key="race-key"))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: _capture(reconcile), range(2)))
    with Session(engine) as session:
        assert sum(isinstance(result, dict) for result in results) == 1
        assert sum(isinstance(result, HTTPException) and result.status_code == 409 for result in results) == 1
        assert len(session.exec(select(AuditEvent).where(AuditEvent.event_name == "onboarding.external_outcome.reconciled")).all()) == 1
        assert len(session.exec(select(OnboardingEvidenceRecord).where(OnboardingEvidenceRecord.run_id == run_id, OnboardingEvidenceRecord.result_code == "SAFE_RETRY_AUTHORIZED")).all()) == 1


def _capture(callable_):  # noqa: ANN001, ANN201
    try:
        return callable_()
    except HTTPException as error:
        return error
