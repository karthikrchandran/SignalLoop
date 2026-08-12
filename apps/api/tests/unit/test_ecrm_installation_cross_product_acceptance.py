from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.ecrm_installations.models import EcrmInstallationBinding
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.secrets import DictSecretResolver
from app.domain.ecrm_installations.service import (
    ConflictingReplay,
    DestinationEnvelope,
    EcrmDestinationService,
    InstallationAuthError,
    InstallationProjectionWorker,
    SuspendedInstallation,
)


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def _binding(key: str, *, status: str = "ACTIVE", source_version: int = 1):
    return EcrmInstallationBinding(
        workspace_id=f"workspace-{key}",
        ecrm_cell_id=f"cell-{key}",
        ecrm_cell_key=key,
        base_url=f"https://{key}.synthetic.invalid",
        credential_secret_ref=f"secret://{key}/v{source_version}",
        capabilities=["WORKFLOW_EVENT"],
        status=status,
        source_version=source_version,
    )


def _event(key: str, version: int, *, event_id: str | None = None, payload=None):
    return DestinationEnvelope(
        source_event_id=event_id or f"ecrm-{key}-{version}",
        source_version=version,
        stream_key="installation:primary",
        event_kind="WORKFLOW_EVENT",
        payload=payload or {"installation": {"cell_key": key, "status": "ACTIVE"}},
    )


def test_two_installations_receive_ack_and_project_without_crossing_workspaces(
    session: Session,
) -> None:
    repository = EcrmInstallationRepository(session)
    repository.save_binding(_binding("ara-global"))
    repository.save_binding(_binding("ai-consulting"))
    session.commit()
    destination = EcrmDestinationService(
        repository,
        DictSecretResolver(
            {
                "secret://ara-global/v1": "ara-credential-v1",
                "secret://ai-consulting/v1": "ai-credential-v1",
            }
        ),
    )

    ara = destination.receive(
        ecrm_cell_id="cell-ara-global",
        credential="ara-credential-v1",
        idempotency_key="ara-installation-1",
        envelope=_event("ara-global", 1),
    )
    ai = destination.receive(
        ecrm_cell_id="cell-ai-consulting",
        credential="ai-credential-v1",
        idempotency_key="ai-installation-1",
        envelope=_event("ai-consulting", 1),
    )
    duplicate = destination.receive(
        ecrm_cell_id="cell-ara-global",
        credential="ara-credential-v1",
        idempotency_key="ara-installation-1",
        envelope=_event("ara-global", 1),
    )
    session.commit()

    assert duplicate.id == ara.id
    assert ai.id != ara.id
    assert {row.workspace_id for row in repository.list_receipts("workspace-ara-global")} == {
        "workspace-ara-global"
    }
    assert InstallationProjectionWorker(repository).run_once(
        workspace_id="workspace-ara-global"
    ) == {"applied": 1, "held": 0, "failed": 0}
    ara_checkpoint = repository.checkpoint(
        "workspace-ara-global", "installation:primary"
    )
    assert ara_checkpoint is not None
    assert ara_checkpoint.source_version == 1
    assert repository.checkpoint("workspace-ai-consulting", "installation:primary") is None


def test_destination_rejects_wrong_cell_credential_workspace_and_conflicting_replay(
    session: Session,
) -> None:
    repository = EcrmInstallationRepository(session)
    repository.save_binding(_binding("ara-global"))
    repository.save_binding(_binding("ai-consulting"))
    session.commit()
    destination = EcrmDestinationService(
        repository,
        DictSecretResolver(
            {
                "secret://ara-global/v1": "ara-credential-v1",
                "secret://ai-consulting/v1": "ai-credential-v1",
            }
        ),
    )

    with pytest.raises(InstallationAuthError):
        destination.receive(
            ecrm_cell_id="cell-ai-consulting",
            credential="ara-credential-v1",
            idempotency_key="cross-cell",
            envelope=_event("ara-global", 1),
        )
    receipt = destination.receive(
        ecrm_cell_id="cell-ara-global",
        credential="ara-credential-v1",
        idempotency_key="ara-installation-1",
        envelope=_event("ara-global", 1),
    )
    session.commit()
    with pytest.raises(ConflictingReplay):
        destination.receive(
            ecrm_cell_id="cell-ara-global",
            credential="ara-credential-v1",
            idempotency_key="ara-installation-1",
            envelope=_event("ara-global", 1, event_id=receipt.source_event_id, payload={"changed": True}),
        )


def test_version_gap_reconciles_without_advancing_other_installation(session: Session) -> None:
    repository = EcrmInstallationRepository(session)
    repository.save_binding(_binding("ara-global"))
    repository.save_binding(_binding("ai-consulting"))
    session.commit()
    destination = EcrmDestinationService(
        repository,
        DictSecretResolver(
            {
                "secret://ara-global/v1": "ara-credential-v1",
                "secret://ai-consulting/v1": "ai-credential-v1",
            }
        ),
    )
    gap = destination.receive(
        ecrm_cell_id="cell-ara-global",
        credential="ara-credential-v1",
        idempotency_key="ara-installation-3",
        envelope=_event("ara-global", 3),
    )
    session.commit()

    assert InstallationProjectionWorker(repository).run_once(
        workspace_id="workspace-ara-global"
    ) == {"applied": 0, "held": 1, "failed": 0}
    assert gap.status == "HELD_GAP"
    candidate = repository.reconcile_stream(
        workspace_id="workspace-ara-global",
        stream_key="installation:primary",
        source_count=3,
        source_checkpoint=3,
    )
    session.commit()
    assert candidate is not None
    assert candidate.workspace_id == "workspace-ara-global"
    assert repository.checkpoint("workspace-ai-consulting", "installation:primary") is None


def test_crash_after_side_effect_is_idempotent_and_suspension_denies_immediately(
    session: Session,
) -> None:
    repository = EcrmInstallationRepository(session)
    binding = repository.save_binding(_binding("ara-global"))
    session.commit()
    destination = EcrmDestinationService(
        repository,
        DictSecretResolver({"secret://ara-global/v1": "ara-credential-v1"}),
    )
    receipt = destination.receive(
        ecrm_cell_id=binding.ecrm_cell_id,
        credential="ara-credential-v1",
        idempotency_key="ara-installation-1",
        envelope=_event("ara-global", 1),
    )
    session.commit()
    claimed = repository.claim_due_receipts(workspace_id=binding.workspace_id)[0]

    with pytest.raises(RuntimeError, match="simulated crash after commit"):
        InstallationProjectionWorker(repository).process(
            receipt.id, fence_token=claimed.fence_token, crash_after_commit=True
        )
    checkpoint = repository.checkpoint(binding.workspace_id, "installation:primary")
    assert checkpoint is not None
    assert checkpoint.applied_count == 1
    assert InstallationProjectionWorker(repository).run_once(
        workspace_id=binding.workspace_id
    ) == {"applied": 0, "held": 0, "failed": 0}

    binding.status = "SUSPENDED"
    binding.updated_at = datetime.now(timezone.utc)
    session.add(binding)
    session.commit()
    with pytest.raises(SuspendedInstallation):
        destination.receive(
            ecrm_cell_id=binding.ecrm_cell_id,
            credential="ara-credential-v1",
            idempotency_key="ara-installation-2",
            envelope=_event("ara-global", 2),
        )


def test_secret_rotation_retires_old_reference_and_keeps_workspace_immutable(
    session: Session,
) -> None:
    repository = EcrmInstallationRepository(session)
    repository.save_binding(_binding("ara-global"))
    session.commit()
    old_destination = EcrmDestinationService(
        repository,
        DictSecretResolver({"secret://ara-global/v1": "ara-credential-v1"}),
    )

    rotated_binding = _binding("ara-global", source_version=2)
    rotated_binding.rotated_at = datetime.now(timezone.utc)
    repository.save_binding(rotated_binding)
    session.commit()
    rotated_destination = EcrmDestinationService(
        repository,
        DictSecretResolver({"secret://ara-global/v2": "ara-credential-v2"}),
    )
    with pytest.raises(InstallationAuthError):
        old_destination.receive(
            ecrm_cell_id=rotated_binding.ecrm_cell_id,
            credential="ara-credential-v1",
            idempotency_key="ara-installation-old",
            envelope=_event("ara-global", 1),
        )
    receipt = rotated_destination.receive(
        ecrm_cell_id=rotated_binding.ecrm_cell_id,
        credential="ara-credential-v2",
        idempotency_key="ara-installation-2",
        envelope=_event("ara-global", 1),
    )
    assert receipt.workspace_id == "workspace-ara-global"
