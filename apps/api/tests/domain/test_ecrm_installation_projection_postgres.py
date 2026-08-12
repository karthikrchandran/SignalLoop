from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, select

from app.core.db import engine
from app.domain.ecrm_installations.models import (
    DestinationReceipt,
    EcrmInstallationBinding,
)
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.secrets import DictSecretResolver
from app.domain.ecrm_installations.service import (
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


def _envelope(suffix: str, *, payload: dict[str, object] | None = None) -> DestinationEnvelope:
    return DestinationEnvelope(
        source_event_id=f"pg-event-{suffix}",
        source_version=1,
        stream_key="installation:primary",
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
        envelope=_envelope(f"available-{suffix}"),
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
