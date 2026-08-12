from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.onboarding.models import OnboardingStage
from app.domain.onboarding.persistence import (
    OnboardingEvidenceBundleRecord,
    OnboardingEvidenceRecord,
    OnboardingRunRecord,
    OnboardingStageRecord,
)
from app.domain.onboarding.persistence_service import (
    _now,
    create_or_resume,
    execute,
    reconcile_unknown_external_outcome,
    retry,
)
from app.domain.onboarding.providers import FakeProviderHub
from app.models import SQLModel as _ModelsLoaded  # noqa: F401


def test_create_is_idempotent_and_stops_at_acceptance() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        first = create_or_resume(session, "ara-global", "key-1", "admin")
        second = create_or_resume(session, "ara-global", "key-1", "admin")
        assert first.id == second.id
        stages = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == first.id)).all()
        assert next(s for s in stages if s.stage == OnboardingStage.READY_FOR_ACCEPTANCE.value).status == "SUCCEEDED"
        assert next(s for s in stages if s.stage == OnboardingStage.ACTIVE.value).status == "PENDING"
        assert first.attempt_count == 2


def test_retry_keeps_run_and_evidence_records() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run = create_or_resume(session, "ai-consulting", "key-2")
        before = len(session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id)).all())
        retried = retry(session, session.get(OnboardingRunRecord, run.id))  # type: ignore[arg-type]
        assert retried.id == run.id
        assert len(session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id)).all()) == before


def test_failed_scoped_canary_preserves_prior_stages_and_is_resumable() -> None:
    class FailedCanary:
        def verify(self, tenant_key: str) -> tuple[str, dict[str, int]]:
            assert tenant_key == "ara-global"
            return "CANARY_FAILED", {"missing": 1, "unexpected": 0}

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run = create_or_resume(session, "ara-global", "key-canary", providers=FakeProviderHub(), canary=FailedCanary())
        stages = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id)).all()
        native = next(stage for stage in stages if stage.stage == OnboardingStage.NATIVE_INTEGRATION_VERIFIED.value)
        assert run.status == "FAILED"
        assert native.status == "FAILED"
        assert native.result_code == "CANARY_FAILED"
        assert next(stage for stage in stages if stage.stage == OnboardingStage.TENANT_DRAFTED.value).status == "SUCCEEDED"
        assert next(stage for stage in stages if stage.stage == OnboardingStage.READY_FOR_ACCEPTANCE.value).status == "PENDING"

        execute(session, run, FakeProviderHub())
        session.commit()
        session.refresh(run)
        assert run.status == "SUCCEEDED"


def test_idempotency_is_scoped_by_tenant_version_and_input_hash() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ara = create_or_resume(session, "ara-global", "shared-key", desired_version="phase1", input_payload={"locale": "en-IN"})
        ai = create_or_resume(session, "ai-consulting", "shared-key", desired_version="phase1", input_payload={"locale": "en-US"})
        changed = create_or_resume(session, "ara-global", "shared-key", desired_version="phase2", input_payload={"locale": "en-IN"})
        assert ara.id != ai.id
        assert ara.id != changed.id


def test_persisted_evidence_is_redacted_and_signed() -> None:
    class SensitiveCanary:
        def verify(self, _tenant_key: str) -> tuple[str, dict[str, object]]:
            return "CANARY_OK", {"missing": 0, "access_token": "raw-token", "provider": {"client_secret": "raw-secret"}}

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run = create_or_resume(session, "ara-global", "safe-evidence", canary=SensitiveCanary(), evidence_signer=Ed25519PrivateKey.generate())
        payloads = [str(record.payload) for record in session.exec(select(OnboardingEvidenceRecord).where(OnboardingEvidenceRecord.run_id == run.id)).all()]
        bundle = session.exec(select(OnboardingEvidenceBundleRecord).where(OnboardingEvidenceBundleRecord.run_id == run.id)).one()
        assert all("raw-token" not in payload and "raw-secret" not in payload for payload in payloads)
        assert "raw-token" not in bundle.canonical_payload and "raw-secret" not in bundle.canonical_payload
        assert bundle.signature and bundle.public_key


def test_expired_running_stage_is_recovered_after_provider_exception() -> None:
    class BrokenProvider(FakeProviderHub):
        def provision_tenant(self, tenant_key: str) -> str:
            raise RuntimeError(f"provider unavailable for {tenant_key}")

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run = create_or_resume(session, "ara-global", "recover-key", providers=BrokenProvider())
        stage = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id, OnboardingStageRecord.stage == OnboardingStage.TENANT_DRAFTED.value)).one()
        assert run.status == "FAILED" and stage.status == "FAILED" and stage.result_code == "PROVIDER_EXCEPTION"
        recovered = retry(session, run)
        assert recovered.status == "SUCCEEDED"
        assert stage.attempt_count == 2


def test_expired_running_lease_requires_reconciliation_then_resumes() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run = create_or_resume(session, "ara-global", "lease-key")
        stage = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id, OnboardingStageRecord.stage == OnboardingStage.NATIVE_INTEGRATION_VERIFIED.value)).one()
        run.status = "RUNNING"
        run.lease_expires_at = _now() - timedelta(seconds=1)
        stage.status = "RUNNING"
        stage.lease_expires_at = _now() - timedelta(seconds=1)
        session.commit()

        assert retry(session, run).status == "FAILED"
        reconcile_unknown_external_outcome(session, run, stage, "NOT_ACCEPTED")
        recovered = retry(session, run)
        assert recovered.status == "SUCCEEDED"
        evidence = session.exec(select(OnboardingEvidenceRecord).where(OnboardingEvidenceRecord.run_id == run.id, OnboardingEvidenceRecord.result_code == "UNKNOWN_EXTERNAL_OUTCOME")).one()
        assert evidence.payload["compensation"] == "NONE_RECONCILE_ON_RETRY"


def test_identical_two_session_requests_converge_on_one_persisted_run(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'onboarding-race.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def request() -> str:
        with Session(engine) as session:
            return str(create_or_resume(session, "ara-global", "race-key", input_payload={"requested_by": "admin"}).id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        run_ids = list(executor.map(lambda _: request(), range(2)))

    with Session(engine) as session:
        assert len(set(run_ids)) == 1
        assert len(session.exec(select(OnboardingRunRecord)).all()) == 1


def test_accepted_then_crash_is_unknown_until_reconciliation_allows_safe_retry() -> None:
    providers = FakeProviderHub(accepted_then_crash_for={"ara-global"})
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run = create_or_resume(session, "ara-global", "unknown-provider", providers=providers)
        stage = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id, OnboardingStageRecord.stage == OnboardingStage.TENANT_DRAFTED.value)).one()
        assert run.status == "FAILED"
        assert stage.result_code == "UNKNOWN_EXTERNAL_OUTCOME"
        assert providers.calls.count("tenant:ara-global") == 1

        retry(session, run, providers=providers)
        assert providers.calls.count("tenant:ara-global") == 1
        reconcile_unknown_external_outcome(session, run, stage, "OPERATOR_APPROVED_SAFE_RETRY")
        retry(session, run, providers=providers)
        assert providers.calls.count("tenant:ara-global") == 2
