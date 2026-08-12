from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, select

from app.core.db import engine
from app.domain.ecrm_installations.models import (
    DestinationReceipt,
    EcrmInstallationBinding,
    InstallationRepairCandidate,
)
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.secrets import DictSecretResolver
from app.domain.ecrm_installations.service import (
    ConflictingReplay,
    DestinationEnvelope,
    EcrmDestinationService,
    InstallationProjectionWorker,
    StaleReceiptFence,
)

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql", reason="requires PostgreSQL locking semantics"
)


@pytest.fixture()
def postgres_session() -> Session:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _binding(suffix: str) -> EcrmInstallationBinding:
    return EcrmInstallationBinding(
        workspace_id=f"pg-install-{suffix}",
        ecrm_cell_id=f"pg-cell-{suffix}",
        ecrm_cell_key=f"pg-key-{suffix}",
        base_url="https://pg-cell.invalid",
        credential_secret_ref=f"secret://{suffix}",
        capabilities=["WORKFLOW_EVENT"],
    )


def _envelope(
    suffix: str,
    *,
    payload: dict[str, object] | None = None,
    stream_key: str = "installation:primary",
) -> DestinationEnvelope:
    return DestinationEnvelope(
        source_event_id=f"pg-event-{suffix}",
        source_version=1,
        stream_key=stream_key,
        event_kind="WORKFLOW_EVENT",
        payload=payload or {"status": "ACTIVE"},
    )


def test_postgres_claim_skips_locked_row_and_recovers_expired_lease(
    postgres_session: Session,
) -> None:
    suffix = uuid4().hex
    binding = _binding(suffix)
    repo = EcrmInstallationRepository(postgres_session)
    repo.save_binding(binding)
    service = EcrmDestinationService(repo, DictSecretResolver({f"secret://{suffix}": "token"}))
    locked = service.receive(
        ecrm_cell_id=binding.ecrm_cell_id,
        credential="token",
        idempotency_key=f"locked-{suffix}",
        envelope=_envelope(f"locked-{suffix}"),
    )
    available = service.receive(
        ecrm_cell_id=binding.ecrm_cell_id,
        credential="token",
        idempotency_key=f"available-{suffix}",
        envelope=_envelope(
            f"available-{suffix}", stream_key="installation:secondary"
        ),
    )
    postgres_session.commit()

    with Session(engine) as locker, Session(engine) as claimant:
        locker.exec(
            select(DestinationReceipt)
            .where(DestinationReceipt.id == locked.id)
            .with_for_update()
        ).one()
        claimed = EcrmInstallationRepository(claimant).claim_due_receipts(
            workspace_id=binding.workspace_id, limit=2, worker_id="worker-a"
        )
        assert [row.id for row in claimed] == [available.id]
        locker.rollback()

    with Session(engine) as session:
        row = session.get(DestinationReceipt, available.id)
        assert row is not None
        stale_fence = row.fence_token
        row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(row)
        session.commit()

    with Session(engine) as session:
        repo = EcrmInstallationRepository(session)
        reclaimed = repo.claim_due_receipts(
            workspace_id=binding.workspace_id, worker_id="worker-b"
        )
        reclaimed_available = next(row for row in reclaimed if row.id == available.id)
        assert reclaimed_available.fence_token == stale_fence + 1
        with pytest.raises(StaleReceiptFence):
            InstallationProjectionWorker(repo).process(available.id, fence_token=stale_fence)


@pytest.mark.parametrize("same_idempotency_key", [True, False])
def test_postgres_concurrent_receipt_replay_returns_one_deterministic_ack(
    postgres_session: Session, same_idempotency_key: bool
) -> None:
    suffix = uuid4().hex
    binding = _binding(suffix)
    EcrmInstallationRepository(postgres_session).save_binding(binding)
    postgres_session.commit()
    barrier = Barrier(2)

    def receive(index: int):
        with Session(engine) as session:
            service = EcrmDestinationService(
                EcrmInstallationRepository(session),
                DictSecretResolver({f"secret://{suffix}": "token"}),
            )
            barrier.wait()
            receipt = service.receive(
                ecrm_cell_id=binding.ecrm_cell_id,
                credential="token",
                idempotency_key=(f"idem-{suffix}" if same_idempotency_key else f"idem-{index}-{suffix}"),
                envelope=_envelope(suffix),
            )
            session.commit()
            return receipt.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(receive, (1, 2)))

    assert ids[0] == ids[1]
    with Session(engine) as session:
        rows = session.exec(
            select(DestinationReceipt).where(
                DestinationReceipt.workspace_id == binding.workspace_id,
                DestinationReceipt.source_event_id == f"pg-event-{suffix}",
            )
        ).all()
        assert len(rows) == 1


def test_postgres_concurrent_conflicting_same_version_keeps_one_receipt(
    postgres_session: Session,
) -> None:
    suffix = uuid4().hex
    binding = _binding(suffix)
    EcrmInstallationRepository(postgres_session).save_binding(binding)
    postgres_session.commit()
    barrier = Barrier(2)

    def receive(index: int):
        with Session(engine) as session:
            service = EcrmDestinationService(
                EcrmInstallationRepository(session),
                DictSecretResolver({f"secret://{suffix}": "token"}),
            )
            barrier.wait()
            try:
                receipt = service.receive(
                    ecrm_cell_id=binding.ecrm_cell_id,
                    credential="token",
                    idempotency_key=f"version-{index}-{suffix}",
                    envelope=DestinationEnvelope(
                        source_event_id=f"version-event-{index}-{suffix}",
                        source_version=1,
                        stream_key="installation:version-conflict",
                        event_kind="WORKFLOW_EVENT",
                        payload={"winner": index},
                    ),
                )
                session.commit()
                return str(receipt.id)
            except ConflictingReplay:
                session.rollback()
                return "CONFLICT"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(receive, (1, 2)))

    assert results.count("CONFLICT") == 1
    with Session(engine) as session:
        rows = session.exec(
            select(DestinationReceipt).where(
                DestinationReceipt.workspace_id == binding.workspace_id,
                DestinationReceipt.stream_key == "installation:version-conflict",
                DestinationReceipt.source_version == 1,
            )
        ).all()
        assert len(rows) == 1


def test_postgres_concurrent_reconciliation_returns_same_candidate(
    postgres_session: Session,
) -> None:
    _ = postgres_session
    suffix = uuid4().hex
    workspace_id = f"pg-reconcile-{suffix}"
    stream_key = "installation:reconcile"
    barrier = Barrier(2)
    insert_barrier = Barrier(2)

    def synchronize_inserts(*_args) -> None:
        insert_barrier.wait()

    def reconcile() -> str:
        with Session(engine) as session:
            repo = EcrmInstallationRepository(session)
            barrier.wait()
            candidate = repo.reconcile_stream(
                workspace_id=workspace_id,
                stream_key=stream_key,
                source_count=2,
                source_checkpoint=3,
            )
            assert candidate is not None
            session.commit()
            return str(candidate.id)

    event.listen(InstallationRepairCandidate, "before_insert", synchronize_inserts)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            candidate_ids = list(executor.map(lambda _index: reconcile(), (1, 2)))
    finally:
        event.remove(InstallationRepairCandidate, "before_insert", synchronize_inserts)

    assert candidate_ids[0] == candidate_ids[1]
    with Session(engine) as session:
        rows = session.exec(
            select(InstallationRepairCandidate).where(
                InstallationRepairCandidate.workspace_id == workspace_id,
                InstallationRepairCandidate.stream_key == stream_key,
            )
        ).all()
        assert len(rows) == 1
