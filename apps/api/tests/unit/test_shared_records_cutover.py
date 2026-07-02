from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes import campaigns as campaign_routes
from app.api.routes import contacts as contact_routes
from app.api.routes.contacts import _upsert_contacts
from app.domain.accounts.service import create_account, update_account
from app.domain.chatbot.models import ChatbotConversation
from app.domain.customer_360 import service as customer_360_service
from app.domain.prospecting import service as prospecting_service
from app.domain.sequences.models import ContactSequenceState
from app.domain.shared_records import service as shared_service
from app.domain.signals.models import SignalEvent
from app.domain.signals.scheduling import SchedulingRequest
from app.domain.voice.models import CallRequest
from app.domain_models import (
    AccountCreate,
    AccountPublic,
    AccountUpdate,
    Campaign,
    CampaignAudienceRequest,
    Contact,
    ContactEvent,
    ContactProgression,
    ContactStateHistory,
    DeadLetterEvent,
    ProspectingSnapshot,
    RoutingDecision,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_contact_import_upserts_shared_record_when_enabled(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        contact_routes.shared_record_service.ecrm_shared_records,
        "get_shared_record",
        lambda record_id: (_ for _ in ()).throw(
            shared_service.EcrmSharedRecordNotFound(record_id)
        ),
    )
    monkeypatch.setattr(
        contact_routes.shared_record_service.ecrm_shared_records,
        "upsert_shared_record",
        lambda payload: calls.append(payload) or {"record": payload, "created": True},
    )

    with _session() as session:
        _upsert_contacts(
            session,
            workspace_id="ws-shared",
            rows=[
                {
                    "email": "ada@example.com",
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                    "company": "Analytical",
                    "phone": "+15551234567",
                    "timezone": "UTC",
                }
            ],
        )
        session.commit()

    assert [call["entityType"] for call in calls] == ["CUSTOMER", "CONTACT"]
    assert calls[0] == {
        "entityType": "CUSTOMER",
        "displayName": "Analytical",
        "status": "active",
        "sourceApp": "emailvoice",
        "emailVoiceLegacyId": str(
            uuid.uuid5(uuid.NAMESPACE_URL, "emailvoice:account:ws-shared:analytical")
        ),
        "externalKey": "emailvoice:account:ws-shared:analytical",
        "companyName": "Analytical",
        "data": {
            "workspaceId": "ws-shared",
            "accountKey": "analytical",
            "websiteUrl": None,
            "industry": None,
            "summary": None,
            "tags": [],
        },
    }
    assert calls[1] == {
        "entityType": "CONTACT",
        "displayName": "Ada Lovelace",
        "status": "active",
        "sourceApp": "emailvoice",
        "emailVoiceLegacyId": str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "emailvoice:contact:ws-shared:ada@example.com",
            )
        ),
        "externalKey": "emailvoice:contact:ws-shared:ada@example.com",
        "email": "ada@example.com",
        "phone": "+15551234567",
        "companyName": "Analytical",
        "parentId": str(
            uuid.uuid5(uuid.NAMESPACE_URL, "emailvoice:account:ws-shared:analytical")
        ),
        "data": {
            "workspaceId": "ws-shared",
            "firstName": "Ada",
            "lastName": "Lovelace",
            "timezone": "UTC",
            "sourceChannel": None,
            "tags": [],
            "intents": [],
        },
    }


def test_contact_read_uses_shared_records_when_enabled(monkeypatch) -> None:
    contact_id = uuid.uuid4()

    def list_shared_contacts(**kwargs: Any) -> list[Contact]:
        assert kwargs == {"workspace_id": "ws-shared", "search": None, "limit": 50}
        return [
            Contact(
                id=contact_id,
                workspace_id="ws-shared",
                email="ada@example.com",
                first_name="Ada",
                last_name="Lovelace",
                company="Analytical",
                phone="+15551234567",
                timezone="UTC",
            )
        ]

    monkeypatch.setattr(
        contact_routes.shared_record_service,
        "list_shared_contacts",
        list_shared_contacts,
    )

    with _session() as session:
        result = contact_routes.read_contacts(session=session, workspace_id="ws-shared")

    assert result.count == 1
    assert result.data[0].id == contact_id
    assert result.data[0].email == "ada@example.com"
    assert result.data[0].first_name == "Ada"
    assert result.data[0].company == "Analytical"


def test_account_create_and_update_upsert_shared_customer_when_enabled(
    monkeypatch,
) -> None:
    calls: list[dict[str, Any]] = []
    store: dict[str, dict[str, Any]] = {}

    def get_shared_record(record_id: str) -> dict[str, Any]:
        record = store.get(record_id)
        if record is None:
            raise shared_service.EcrmSharedRecordNotFound(record_id)
        return record

    def upsert_shared_record(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        record_id = str(payload["emailVoiceLegacyId"])
        store[record_id] = {"record": payload, "created": record_id not in store}
        return store[record_id]

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
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "list_shared_records",
        lambda **kwargs: {"records": []},
    )

    with _session() as session:
        account = create_account(
            session,
            workspace_id="ws-shared",
            data=AccountCreate(name="Analytical", industry="Education"),
        )
        updated = update_account(
            session,
            workspace_id="ws-shared",
            account_id=account.id,
            data=AccountUpdate(name="Analytical Engines", status="active"),
        )

    assert account.name == "Analytical"
    assert updated is not None
    assert updated.name == "Analytical Engines"
    assert [call["displayName"] for call in calls] == [
        "Analytical",
        "Analytical Engines",
    ]
    assert calls[0]["entityType"] == "CUSTOMER"
    assert calls[0]["emailVoiceLegacyId"] == str(account.id)
    assert calls[0]["externalKey"] == "emailvoice:account:ws-shared:analytical"
    assert calls[1]["externalKey"] == "emailvoice:account:ws-shared:analytical-engines"


def test_shared_contact_service_maps_records_without_local_contact_lookup(
    monkeypatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def list_shared_records(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "records": [
                {
                    "id": "shared-contact-1",
                    "entityType": "CONTACT",
                    "displayName": "Ada Lovelace",
                    "status": "active",
                    "email": "ada@example.com",
                    "phone": "+15551234567",
                    "companyName": "Analytical",
                    "data": {
                        "workspaceId": "ws-shared",
                        "firstName": "Ada",
                        "lastName": "Lovelace",
                        "timezone": "UTC",
                    },
                    "createdAt": "2026-06-30T12:00:00Z",
                }
            ]
        }

    monkeypatch.setattr(
        shared_service.ecrm_shared_records, "list_shared_records", list_shared_records
    )

    contacts = shared_service.list_shared_contacts(
        workspace_id="ws-shared", search="Ada", limit=10
    )

    assert calls == [
        {"entity_type": "CONTACT", "q": "Ada", "status": "active", "limit": 10}
    ]
    assert len(contacts) == 1
    assert contacts[0].email == "ada@example.com"
    assert contacts[0].first_name == "Ada"
    assert contacts[0].company == "Analytical"


def test_shared_account_service_maps_customer_and_child_contacts(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    def list_shared_records(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        if kwargs["entity_type"] == "CUSTOMER":
            return {
                "records": [
                    {
                        "id": "shared-customer-1",
                        "entityType": "CUSTOMER",
                        "displayName": "Analytical",
                        "status": "active",
                        "companyName": "Analytical",
                        "data": {
                            "workspaceId": "ws-shared",
                            "accountKey": "analytical",
                            "industry": "Education",
                            "summary": "Shared customer",
                            "tags": ["priority"],
                        },
                        "createdAt": "2026-06-30T12:00:00Z",
                        "updatedAt": "2026-06-30T12:30:00Z",
                    }
                ]
            }
        return {
            "records": [
                {
                    "id": "shared-contact-1",
                    "entityType": "CONTACT",
                    "displayName": "Ada Lovelace",
                    "status": "active",
                    "parentId": "shared-customer-1",
                    "email": "ada@example.com",
                    "companyName": "Analytical",
                    "data": {
                        "workspaceId": "ws-shared",
                        "firstName": "Ada",
                        "timezone": "UTC",
                    },
                    "createdAt": "2026-06-30T12:00:00Z",
                }
            ]
        }

    monkeypatch.setattr(
        shared_service.ecrm_shared_records, "list_shared_records", list_shared_records
    )

    accounts = shared_service.list_shared_accounts(
        workspace_id="ws-shared", search=None, limit=50
    )
    profile = shared_service.get_shared_account_profile(
        workspace_id="ws-shared",
        account_id=accounts[0].id,
    )

    assert accounts[0].name == "Analytical"
    assert accounts[0].contact_count == 1
    assert profile is not None
    assert profile.account.name == "Analytical"
    assert profile.contacts[0].email == "ada@example.com"
    assert [call["entity_type"] for call in calls] == [
        "CUSTOMER",
        "CONTACT",
        "CUSTOMER",
        "CONTACT",
    ]


def test_customer_360_accounts_read_from_shared_layer_when_enabled(monkeypatch) -> None:
    account_id = uuid.uuid4()
    account = AccountPublic(
        id=account_id,
        workspace_id="ws-shared",
        name="Analytical",
        account_key="analytical",
        status="active",
        tags=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    def load_accounts(**kwargs: Any) -> list[AccountPublic]:
        assert kwargs == {"workspace_id": "ws-shared", "search": "ana", "limit": 10}
        return [account]

    def load_contacts(**kwargs: Any) -> list[Contact]:
        assert kwargs == {"workspace_id": "ws-shared", "account_id": account_id}
        return [
            Contact(
                id=uuid.uuid4(),
                workspace_id="ws-shared",
                email="ada@example.com",
                first_name="Ada",
                company="Analytical",
                timezone="UTC",
            ),
            Contact(
                id=uuid.uuid4(),
                workspace_id="ws-shared",
                email="grace@example.com",
                first_name="Grace",
                company="Analytical",
                timezone="UTC",
            ),
        ]

    monkeypatch.setattr(
        customer_360_service,
        "_load_accounts",
        load_accounts,
    )
    monkeypatch.setattr(
        customer_360_service,
        "_load_contacts",
        load_contacts,
    )

    with _session() as session:
        result = customer_360_service.list_customer_360_accounts(
            session,
            workspace_id="ws-shared",
            search="ana",
            limit=10,
        )

    assert result.count == 1
    assert result.data[0].id == account_id
    assert result.data[0].contact_count == 2


def test_prospecting_ready_contacts_read_from_shared_layer_when_enabled(
    monkeypatch,
) -> None:
    contact_id = uuid.uuid4()

    def list_shared_contacts(**kwargs: Any) -> list[Contact]:
        assert kwargs == {"workspace_id": "ws-shared", "search": "ada", "limit": 200}
        return [
            Contact(
                id=contact_id,
                workspace_id="ws-shared",
                email="ada@example.com",
                first_name="Ada",
                last_name="Lovelace",
                company="Analytical",
                phone="+15551234567",
                timezone="UTC",
            )
        ]

    monkeypatch.setattr(
        prospecting_service.shared_record_service,
        "list_shared_contacts",
        list_shared_contacts,
    )

    with _session() as session:
        result = prospecting_service.list_ready_contacts(
            session,
            workspace_id="ws-shared",
            search="ada",
            limit=20,
        )

    assert len(result) == 1
    assert result[0].id == contact_id
    assert result[0].email == "ada@example.com"
    assert result[0].company == "Analytical"


def test_campaign_audience_reads_shared_contacts_when_enabled(monkeypatch) -> None:
    contact_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    def list_shared_contacts(**kwargs: Any) -> list[Contact]:
        assert kwargs == {"workspace_id": "ws-shared", "search": None, "limit": 100}
        return [
            Contact(
                id=contact_id,
                workspace_id="ws-shared",
                email="ada@example.com",
                first_name="Ada",
                company="Analytical",
                timezone="UTC",
            )
        ]

    monkeypatch.setattr(
        campaign_routes.shared_record_service,
        "list_shared_contacts",
        list_shared_contacts,
    )

    with _session() as session:
        campaign = Campaign(
            name="Shared Audience", workspace_id="ws-shared", created_by=owner_id
        )
        session.add(campaign)
        session.commit()
        session.refresh(campaign)

        result = campaign_routes.assign_existing_contacts_to_campaign(
            session=session,
            current_user=SimpleNamespace(id=owner_id, is_superuser=True),
            campaign_id=campaign.id,
            workspace_id="ws-shared",
            body=CampaignAudienceRequest(include_all_contacts=True),
        )

        progressions = session.exec(select(ContactProgression)).all()

    assert result.selected_count == 1
    assert result.added_count == 1
    assert progressions[0].contact_id == contact_id


def test_prospecting_snapshot_reads_selected_contact_from_shared_layer(
    monkeypatch,
) -> None:
    contact_id = uuid.uuid4()

    async def website_sources(_: str | None) -> list[Any]:
        return []

    monkeypatch.setattr(prospecting_service, "_website_sources", website_sources)

    def get_shared_contact(**kwargs: Any) -> Contact:
        assert kwargs == {"workspace_id": "ws-shared", "contact_id": contact_id}
        return Contact(
            id=contact_id,
            workspace_id="ws-shared",
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
            company="Analytical",
            phone="+15551234567",
            timezone="UTC",
        )

    monkeypatch.setattr(
        prospecting_service.shared_record_service,
        "get_shared_contact",
        get_shared_contact,
    )

    with _session() as session:
        snapshot = asyncio.run(
            prospecting_service.create_prospecting_snapshot(
                session=session,
                workspace_id="ws-shared",
                contact_id=contact_id,
                company_url=None,
                actor_id=None,
                actor_role=None,
            )
        )

    assert snapshot.contact_id == contact_id
    assert snapshot.email_draft


def test_operational_models_expose_shared_reference_attributes() -> None:
    shared_account_id = uuid.uuid4()
    shared_contact_id = uuid.uuid4()

    assert Contact.__table__.columns["account_id"].key == "account_id"
    assert Contact.model_fields["shared_account_id"].annotation == uuid.UUID | None
    compatibility_contact = Contact(
        workspace_id="ws-shared",
        shared_account_id=shared_account_id,
        email="compat@example.com",
        timezone="UTC",
    )
    assert compatibility_contact.shared_account_id == shared_account_id
    assert compatibility_contact.account_id == shared_account_id

    contact_instances = [
        ProspectingSnapshot(
            workspace_id="ws-shared",
            shared_contact_id=shared_contact_id,
            email_draft="draft",
            voice_opener="hello",
        ),
        ContactProgression(
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            current_state="inbox",
        ),
        ContactStateHistory(
            workspace_id="ws-shared",
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            from_state="inbox",
            to_state="engaged",
        ),
        ContactEvent(
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            workspace_id="ws-shared",
            event_type="opened",
        ),
        RoutingDecision(
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            workspace_id="ws-shared",
            decision_type="sequence_step",
        ),
        DeadLetterEvent(
            action_queue_id=uuid.uuid4(),
            campaign_id=uuid.uuid4(),
            shared_contact_id=shared_contact_id,
            workspace_id="ws-shared",
            action_type="send_email",
        ),
        ContactSequenceState(
            shared_contact_id=shared_contact_id,
            sequence_id=uuid.uuid4(),
        ),
        SignalEvent(
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            channel="email",
            signal_type="reply",
        ),
        SchedulingRequest(
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            signal_event_id=uuid.uuid4(),
        ),
        CallRequest(
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            voice_script_id=uuid.uuid4(),
            trigger_reason="manual_test_call",
            scheduled_at=datetime.now(timezone.utc),
        ),
        ChatbotConversation(
            workspace_id="ws-shared",
            channel_type="whatsapp_business",
            visitor_id="visitor-1",
            shared_contact_id=shared_contact_id,
        ),
    ]

    for instance in contact_instances:
        model = type(instance)
        assert model.__table__.columns["contact_id"].key == "contact_id"
        assert model.model_fields["shared_contact_id"].annotation in {
            uuid.UUID,
            uuid.UUID | None,
        }
        assert instance.shared_contact_id == shared_contact_id
        assert instance.contact_id == shared_contact_id
