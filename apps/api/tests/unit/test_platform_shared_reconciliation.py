from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.shared_records import service as shared_service
from app.domain.shared_records.reconciliation import reconcile_counts
from app.domain.shared_records.repository import PlatformSharedRepository


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_reconcile_counts_reports_expected_fields_for_mismatch() -> None:
    report = reconcile_counts(
        ecrm_counts={"CUSTOMER": 2, "CONTACT": 5},
        local_counts={"CUSTOMER": 2, "CONTACT": 4},
    )

    assert report == {
        "status": "mismatch",
        "diffs": [{"entity": "CONTACT", "expected": 5, "actual": 4}],
        "ecrm_counts": {"CUSTOMER": 2, "CONTACT": 5, "LEAD": 0, "ORDER": 0},
        "local_counts": {"CUSTOMER": 2, "CONTACT": 4, "LEAD": 0, "ORDER": 0},
    }


def test_reconcile_with_ecrm_counts_only_active_workspace_records_using_export_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    responses = {
        ("CUSTOMER", None): {
            "items": [
                {
                    "id": "customer-1",
                    "status": "active",
                    "data": {"workspaceId": "ws-1"},
                },
                {
                    "id": "customer-2",
                    "status": "inactive",
                    "data": {"workspaceId": "ws-1"},
                },
                {
                    "id": "customer-3",
                    "status": "active",
                    "data": {"workspaceId": "ws-2"},
                },
            ],
            "nextCursor": "customer-cursor-2",
        },
        ("CUSTOMER", "customer-cursor-2"): {
            "items": [
                {
                    "id": "customer-4",
                    "status": "active",
                    "data": {"workspaceId": "ws-1"},
                }
            ],
            "nextCursor": None,
        },
        ("CONTACT", None): {
            "items": [
                {
                    "id": "contact-1",
                    "status": "active",
                    "data": {"workspaceId": "ws-1"},
                },
                {
                    "id": "contact-2",
                    "status": "active",
                    "data": {"workspaceId": "ws-2"},
                },
            ],
            "nextCursor": "contact-cursor-2",
        },
        ("CONTACT", "contact-cursor-2"): {
            "items": [
                {
                    "id": "contact-3",
                    "status": "active",
                    "data": {"workspaceId": "ws-1"},
                },
                {
                    "id": "contact-4",
                    "status": "inactive",
                    "data": {"workspaceId": "ws-1"},
                },
            ],
            "nextCursor": None,
        },
        ("LEAD", None): {"items": [], "nextCursor": None},
        ("ORDER", None): {"items": [], "nextCursor": None},
    }

    def fake_list_shared_records_export_page(
        *,
        entity_type: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, object]:
        calls.append(
            {
                "entity_type": entity_type,
                "cursor": cursor,
                "limit": limit,
            }
        )
        return responses[(str(entity_type), cursor)]

    monkeypatch.setattr(
        "app.domain.shared_records.reconciliation.ecrm_shared_records.list_shared_records_export_page",
        fake_list_shared_records_export_page,
    )

    with _session() as session:
        repo = PlatformSharedRepository(session)

        active_account_1 = repo.upsert_account(
            workspace_id="ws-1",
            external_key="emailvoice:account:ws-1:acme",
            display_name="Acme",
            status="active",
            source_app="emailvoice",
            source_record_id=str(uuid.uuid4()),
        )
        active_account_2 = repo.upsert_account(
            workspace_id="ws-1",
            external_key="emailvoice:account:ws-1:beta",
            display_name="Beta",
            status="active",
            source_app="emailvoice",
            source_record_id=str(uuid.uuid4()),
        )
        repo.upsert_account(
            workspace_id="ws-1",
            external_key="emailvoice:account:ws-1:inactive",
            display_name="Inactive",
            status="inactive",
            source_app="emailvoice",
            source_record_id=str(uuid.uuid4()),
        )
        ws2_account = repo.upsert_account(
            workspace_id="ws-2",
            external_key="emailvoice:account:ws-2:gamma",
            display_name="Gamma",
            status="active",
            source_app="emailvoice",
            source_record_id=str(uuid.uuid4()),
        )

        repo.upsert_contact(
            workspace_id="ws-1",
            external_key="emailvoice:contact:ws-1:ada@example.com",
            display_name="Ada Lovelace",
            email="ada@example.com",
            status="active",
            parent_account_id=active_account_1.id,
            source_app="emailvoice",
            source_record_id=str(uuid.uuid4()),
        )
        repo.upsert_contact(
            workspace_id="ws-1",
            external_key="emailvoice:contact:ws-1:grace@example.com",
            display_name="Grace Hopper",
            email="grace@example.com",
            status="active",
            parent_account_id=active_account_2.id,
            source_app="emailvoice",
            source_record_id=str(uuid.uuid4()),
        )
        repo.upsert_contact(
            workspace_id="ws-1",
            external_key="emailvoice:contact:ws-1:inactive@example.com",
            display_name="Inactive Contact",
            email="inactive@example.com",
            status="inactive",
            parent_account_id=active_account_1.id,
            source_app="emailvoice",
            source_record_id=str(uuid.uuid4()),
        )
        repo.upsert_contact(
            workspace_id="ws-2",
            external_key="emailvoice:contact:ws-2:ws2@example.com",
            display_name="Workspace Two",
            email="ws2@example.com",
            status="active",
            parent_account_id=ws2_account.id,
            source_app="emailvoice",
            source_record_id=str(uuid.uuid4()),
        )
        session.commit()

        report = shared_service.reconcile_with_ecrm(
            workspace_id="ws-1",
            session=session,
        )

    assert calls == [
        {"entity_type": "CUSTOMER", "cursor": None, "limit": 500},
        {
            "entity_type": "CUSTOMER",
            "cursor": "customer-cursor-2",
            "limit": 500,
        },
        {"entity_type": "CONTACT", "cursor": None, "limit": 500},
        {
            "entity_type": "CONTACT",
            "cursor": "contact-cursor-2",
            "limit": 500,
        },
        {"entity_type": "LEAD", "cursor": None, "limit": 500},
        {"entity_type": "ORDER", "cursor": None, "limit": 500},
    ]
    assert report == {
        "status": "ok",
        "diffs": [],
        "ecrm_counts": {"CUSTOMER": 2, "CONTACT": 2, "LEAD": 0, "ORDER": 0},
        "local_counts": {"CUSTOMER": 2, "CONTACT": 2, "LEAD": 0, "ORDER": 0},
    }
