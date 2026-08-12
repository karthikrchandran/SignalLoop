from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.ecrm_installations.client import (
    CellDeliveryResponse,
    EcrmCellClient,
    EcrmCellUnavailable,
)
from app.domain.ecrm_installations.models import (
    EcrmInstallationBinding,
    InstallationRepairCandidate,
    RevenueOsInstallationProjection,
)
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.secrets import DictSecretResolver, EnvSecretResolver
from app.domain.ecrm_installations.service import (
    ConflictingReplay,
    DestinationEnvelope,
    EcrmDestinationService,
    InstallationAuthError,
    InstallationProjectionWorker,
    SuspendedInstallation,
)
from app.domain.tenants.models import ProductCode, Tenant, TenantEntitlement


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def _binding(workspace_id: str, *, status: str = "ACTIVE") -> EcrmInstallationBinding:
    return EcrmInstallationBinding(
        workspace_id=workspace_id,
        ecrm_cell_id=f"cell-{workspace_id}",
        ecrm_cell_key=f"key-{workspace_id}",
        base_url=f"https://{workspace_id}.crm.invalid",
        credential_secret_ref=f"secret://{workspace_id}",
        capabilities=["SHARED_RECORD", "WORKFLOW_EVENT"],
        status=status,
        source_version=1,
    )


def _envelope(*, event_id: str = "evt-1", version: int = 1, payload: dict | None = None) -> DestinationEnvelope:
    return DestinationEnvelope(
        source_event_id=event_id,
        source_version=version,
        stream_key="installation:primary",
        event_kind="WORKFLOW_EVENT",
        payload=payload or {"installation": {"status": "ACTIVE"}},
    )


def test_repository_is_workspace_scoped(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    repo.save_binding(_binding("ws-b"))
    session.commit()

    assert repo.get_binding("ws-a").ecrm_cell_id == "cell-ws-a"
    assert repo.get_binding("ws-a", ecrm_cell_id="cell-ws-b") is None
    assert repo.list_receipts("ws-a") == []


def test_destination_auth_derives_workspace_from_cell_binding(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    repo.save_binding(_binding("ws-b"))
    session.commit()
    service = EcrmDestinationService(repo, DictSecretResolver({"secret://ws-a": "token-a", "secret://ws-b": "token-b"}))

    receipt = service.receive(
        ecrm_cell_id="cell-ws-a",
        credential="token-a",
        idempotency_key="idem-1",
        envelope=_envelope(),
    )
    session.commit()

    assert receipt.workspace_id == "ws-a"
    assert receipt.ecrm_cell_id == "cell-ws-a"
    assert service.receive(
        ecrm_cell_id="cell-ws-a",
        credential="token-a",
        idempotency_key="idem-1",
        envelope=_envelope(),
    ).id == receipt.id


@pytest.mark.parametrize(
    ("cell_id", "credential"),
    [("cell-missing", "token-a"), ("cell-ws-a", "wrong")],
)
def test_destination_rejects_wrong_cell_or_credential(
    session: Session, cell_id: str, credential: str
) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    session.commit()
    service = EcrmDestinationService(repo, DictSecretResolver({"secret://ws-a": "token-a"}))

    with pytest.raises(InstallationAuthError):
        service.receive(
            ecrm_cell_id=cell_id,
            credential=credential,
            idempotency_key="idem-1",
            envelope=_envelope(),
        )


def test_destination_rejects_conflicting_replay(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    session.commit()
    service = EcrmDestinationService(repo, DictSecretResolver({"secret://ws-a": "token-a"}))
    service.receive(
        ecrm_cell_id="cell-ws-a",
        credential="token-a",
        idempotency_key="idem-1",
        envelope=_envelope(payload={"value": 1}),
    )

    with pytest.raises(ConflictingReplay):
        service.receive(
            ecrm_cell_id="cell-ws-a",
            credential="token-a",
            idempotency_key="idem-1",
            envelope=_envelope(payload={"value": 2}),
        )


def test_suspended_binding_rejects_delivery(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a", status="SUSPENDED"))
    session.commit()
    service = EcrmDestinationService(repo, DictSecretResolver({"secret://ws-a": "token-a"}))

    with pytest.raises(SuspendedInstallation):
        service.receive(
            ecrm_cell_id="cell-ws-a",
            credential="token-a",
            idempotency_key="idem-1",
            envelope=_envelope(),
        )


def test_worker_applies_in_order_and_holds_gap(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    session.commit()
    destination = EcrmDestinationService(repo, DictSecretResolver({"secret://ws-a": "token-a"}))
    for envelope in (_envelope(event_id="evt-1", version=1), _envelope(event_id="evt-3", version=3)):
        destination.receive(
            ecrm_cell_id="cell-ws-a",
            credential="token-a",
            idempotency_key=envelope.source_event_id,
            envelope=envelope,
        )
    session.commit()

    worker = InstallationProjectionWorker(repo)
    assert worker.run_once(limit=10) == {"applied": 1, "held": 1, "failed": 0}
    receipts = {row.source_version: row for row in repo.list_receipts("ws-a")}
    assert receipts[1].status == "APPLIED"
    assert receipts[3].status == "HELD_GAP"


def test_projection_persists_when_revenueos_disabled_but_reads_are_gated(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    tenant = Tenant(key="ws-a", display_name="Workspace A")
    session.add(tenant)
    session.commit()
    destination = EcrmDestinationService(repo, DictSecretResolver({"secret://ws-a": "token-a"}))
    destination.receive(
        ecrm_cell_id="cell-ws-a",
        credential="token-a",
        idempotency_key="evt-1",
        envelope=_envelope(),
    )
    session.commit()

    InstallationProjectionWorker(repo).run_once()
    assert session.exec(select(RevenueOsInstallationProjection)).one().workspace_id == "ws-a"
    assert repo.get_revenueos_projection("ws-a") is None

    session.add(TenantEntitlement(tenant_id=tenant.id, product_code=ProductCode.REVENUE_OS, status="ACTIVE"))
    session.commit()
    assert repo.get_revenueos_projection("ws-a").source_version == 1


def test_worker_is_cross_workspace_safe_and_same_version_is_noop(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    for workspace_id in ("ws-a", "ws-b"):
        repo.save_binding(_binding(workspace_id))
    session.commit()
    destination = EcrmDestinationService(
        repo,
        DictSecretResolver({"secret://ws-a": "token-a", "secret://ws-b": "token-b"}),
    )
    for workspace_id in ("ws-a", "ws-b"):
        destination.receive(
            ecrm_cell_id=f"cell-{workspace_id}",
            credential=f"token-{workspace_id[-1]}",
            idempotency_key=f"evt-{workspace_id}",
            envelope=_envelope(event_id=f"evt-{workspace_id}"),
        )
    session.commit()

    worker = InstallationProjectionWorker(repo)
    assert worker.run_once(workspace_id="ws-a") == {"applied": 1, "held": 0, "failed": 0}
    assert repo.list_receipts("ws-b")[0].status == "RECEIVED"
    assert worker.run_once(workspace_id="ws-a") == {"applied": 0, "held": 0, "failed": 0}


def test_retry_exhaustion_and_replay(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    session.commit()
    destination = EcrmDestinationService(repo, DictSecretResolver({"secret://ws-a": "token-a"}))
    receipt = destination.receive(
        ecrm_cell_id="cell-ws-a",
        credential="token-a",
        idempotency_key="evt-1",
        envelope=_envelope(payload={"force_error": True}),
    )
    session.commit()
    worker = InstallationProjectionWorker(repo, max_attempts=2)

    worker.run_once()
    receipt.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.add(receipt)
    session.commit()
    worker.run_once()
    session.refresh(receipt)
    assert receipt.status == "DEAD_LETTER"

    receipt.payload = {**receipt.payload, "force_error": False}
    repo.replay_receipt("ws-a", receipt.id)
    session.commit()
    assert worker.run_once() == {"applied": 1, "held": 0, "failed": 0}


def test_crash_after_projection_insert_is_idempotently_recovered(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    session.commit()
    destination = EcrmDestinationService(repo, DictSecretResolver({"secret://ws-a": "token-a"}))
    receipt = destination.receive(
        ecrm_cell_id="cell-ws-a",
        credential="token-a",
        idempotency_key="evt-1",
        envelope=_envelope(),
    )
    session.commit()
    worker = InstallationProjectionWorker(repo)

    with pytest.raises(RuntimeError, match="simulated crash"):
        worker.process(receipt.id, crash_after_side_effect=True)
    session.expire_all()
    assert session.exec(select(RevenueOsInstallationProjection)).one().source_event_id == "evt-1"
    assert worker.process(receipt.id).status == "APPLIED"


def test_reconciliation_creates_one_deduplicated_repair_candidate(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    session.commit()

    first = repo.reconcile_stream(
        workspace_id="ws-a",
        stream_key="installation:primary",
        source_count=2,
        source_checkpoint=3,
    )
    second = repo.reconcile_stream(
        workspace_id="ws-a",
        stream_key="installation:primary",
        source_count=2,
        source_checkpoint=3,
    )

    assert first.id == second.id
    assert session.exec(select(InstallationRepairCandidate)).all() == [first]
    repo.resolve_repair("ws-a", first.id, resolution="REPLAY_REQUESTED")
    assert first.status == "RESOLVED"


def test_cell_client_uses_only_persisted_binding_and_operational_headers(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    session.commit()
    calls: list[tuple[str, dict[str, str], float]] = []

    class Transport:
        def post(self, url: str, *, json: dict, headers: dict[str, str], timeout: float) -> CellDeliveryResponse:
            calls.append((url, headers, timeout))
            return CellDeliveryResponse(202, {"event_id": json["source_event_id"]})

    client = EcrmCellClient(repo, DictSecretResolver({"secret://ws-a": "token-a"}), Transport())
    response = client.send(
        workspace_id="ws-a",
        source_event_id="evt-1",
        source_version=1,
        event_kind="WORKFLOW_EVENT",
        stream_key="installation:primary",
        payload={"ok": True},
        correlation_id="corr-1",
        deadline_seconds=4.0,
    )

    assert response.status_code == 202
    assert calls == [
        (
            "https://ws-a.crm.invalid/api/integrations/signalloop/deliveries",
            {
                "Authorization": "Bearer token-a",
                "Idempotency-Key": "evt-1",
                "X-Correlation-Id": "corr-1",
                "X-ECRM-Cell-Id": "cell-ws-a",
                "X-ECRM-Cell-Key": "key-ws-a",
            },
            4.0,
        )
    ]


def test_cell_client_opens_circuit_after_failures(session: Session) -> None:
    repo = EcrmInstallationRepository(session)
    repo.save_binding(_binding("ws-a"))
    session.commit()

    class FailingTransport:
        def post(self, *args, **kwargs):
            raise httpx.ConnectError("offline")

    client = EcrmCellClient(
        repo,
        DictSecretResolver({"secret://ws-a": "token-a"}),
        FailingTransport(),
        circuit_threshold=2,
    )
    kwargs = {
        "workspace_id": "ws-a",
        "source_event_id": "evt-1",
        "source_version": 1,
        "event_kind": "WORKFLOW_EVENT",
        "stream_key": "installation:primary",
        "payload": {},
        "correlation_id": "corr-1",
    }
    with pytest.raises(httpx.ConnectError):
        client.send(**kwargs)
    with pytest.raises(httpx.ConnectError):
        client.send(**kwargs)
    with pytest.raises(EcrmCellUnavailable):
        client.send(**kwargs)
    assert repo.get_binding("ws-a").status == "DEGRADED"


def test_production_secret_resolver_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ECRM_CELL_SECRET", raising=False)
    resolver = EnvSecretResolver()
    with pytest.raises(LookupError):
        resolver.resolve("env://ECRM_CELL_SECRET")
    with pytest.raises(ValueError):
        resolver.resolve("plaintext-token")
