from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.onboarding.models import OnboardingStage
from app.domain.onboarding.persistence import OnboardingRunRecord, OnboardingStageRecord
from app.domain.onboarding.persistence_service import create_or_resume, retry
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
