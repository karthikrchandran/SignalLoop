from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch
from sqlmodel import Session, SQLModel, create_engine

from app.domain.accounts.service import (
    account_to_public,
    find_or_create_account_for_company,
    generate_account_key,
)
from app.domain.shared_records import service as shared_service
from app.domain_models import (
    AccountContactAssignment,
    AccountContactAssignmentPublic,
    AccountPublic,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_generate_account_key_normalizes_company_name() -> None:
    assert (
        generate_account_key("  Analytical Health, Inc.  ") == "analytical-health-inc"
    )
    assert generate_account_key("ACME___Clinic!!!") == "acme-clinic"


def test_find_or_create_account_reuses_account_by_workspace_and_key(
    monkeypatch: MonkeyPatch,
) -> None:
    store: dict[str, dict[str, object]] = {}

    def get_shared_record(record_id: str) -> dict[str, object]:
        record = store.get(record_id)
        if record is None:
            raise shared_service.EcrmSharedRecordNotFound(record_id)
        return record

    def upsert_shared_record(payload: dict[str, object]) -> dict[str, object]:
        store[str(payload["emailVoiceLegacyId"])] = {"record": payload, "created": True}
        return store[str(payload["emailVoiceLegacyId"])]

    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "get_shared_record",
        get_shared_record,
    )
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "upsert_shared_record",
        upsert_shared_record,
    )

    with _session() as session:
        first = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name="Analytical Health, Inc.",
        )
        second = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name="Analytical Health Inc",
        )
        other_workspace = find_or_create_account_for_company(
            session,
            workspace_id="ws-b",
            company_name="Analytical Health Inc",
        )

    assert first is not None
    assert second is not None
    assert other_workspace is not None
    assert first.id == second.id
    assert first.name == "Analytical Health, Inc."
    assert first.account_key == "analytical-health-inc"
    assert other_workspace.workspace_id == "ws-b"
    assert other_workspace.id != first.id


def test_find_or_create_account_reselects_after_duplicate_key_race(
    monkeypatch: MonkeyPatch,
) -> None:
    existing_id = uuid.uuid5(
        uuid.NAMESPACE_URL, "emailvoice:account:ws-a:analytical-health-inc"
    )
    store = {
        str(existing_id): {
            "record": {
                "id": str(existing_id),
                "entityType": "CUSTOMER",
                "displayName": "Analytical Health Inc",
                "status": "active",
                "companyName": "Analytical Health Inc",
                "emailVoiceLegacyId": str(existing_id),
                "data": {
                    "workspaceId": "ws-a",
                    "accountKey": "analytical-health-inc",
                },
                "createdAt": "2026-06-30T12:00:00Z",
                "updatedAt": "2026-06-30T12:00:00Z",
            },
            "created": False,
        }
    }

    def get_shared_record(record_id: str) -> dict[str, object]:
        record = store.get(record_id)
        if record is None:
            raise shared_service.EcrmSharedRecordNotFound(record_id)
        return record

    def upsert_shared_record(payload: dict[str, object]) -> dict[str, object]:
        record_id = str(payload["emailVoiceLegacyId"])
        store[record_id] = {"record": payload, "created": record_id not in store}
        return store[record_id]

    monkeypatch.setattr(shared_service.ecrm_shared_records, "get_shared_record", get_shared_record)
    monkeypatch.setattr(shared_service.ecrm_shared_records, "upsert_shared_record", upsert_shared_record)

    with _session() as session:
        account = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name="Analytical Health, Inc.",
        )

    assert account is not None
    assert account.id == existing_id


def test_find_or_create_account_ignores_blank_company() -> None:
    with _session() as session:
        account = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name=" ",
        )

    assert account is None


def test_account_to_public_maps_fields() -> None:
    account = AccountPublic(
        id=uuid.uuid4(),
        workspace_id="ws-a",
        name="Analytical Health",
        account_key="analytical-health",
        website_url="https://analytical.example",
        industry="Healthcare",
        status="active",
        summary="Multi-location buyer.",
        tags=["pricing", "voice-ready"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    public = account_to_public(account)

    assert public.name == "Analytical Health"
    assert public.website_url == "https://analytical.example"
    assert public.tags == ["pricing", "voice-ready"]


def test_account_contact_assignment_schema_matches_plan() -> None:
    contact_id = uuid.uuid4()

    assignment = AccountContactAssignment(contact_ids=[contact_id])
    public = AccountContactAssignmentPublic(account_id=uuid.uuid4())

    assert assignment.contact_ids == [contact_id]
    assert public.assigned_count == 0
    assert public.unassigned_count == 0
    assert public.contact_ids == []
    with pytest.raises(ValidationError):
        AccountContactAssignment(contact_ids=[])
