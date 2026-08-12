from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.onboarding.models import OnboardingStage
from app.domain.onboarding.persistence import OnboardingRunRecord, OnboardingStageRecord
from app.domain.onboarding.persistence_service import create_or_resume, execute, retry
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
