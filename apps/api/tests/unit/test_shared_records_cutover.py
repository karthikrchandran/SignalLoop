from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes import accounts as account_routes
from app.api.routes import campaigns as campaign_routes
from app.api.routes import contacts as contact_routes
from app.api.routes.contacts import _upsert_contacts
from app.domain import accounts as accounts_domain
from app.domain.accounts.service import (
    assign_contacts_to_account,
    create_account,
    unassign_contact_from_account,
    update_account,
)
from app.domain.chatbot.models import ChatbotConversation
from app.domain.customer_360 import service as customer_360_service
from app.domain.prospecting import service as prospecting_service
from app.domain.sequences.models import ContactSequenceState
from app.domain.shared_records import service as shared_service
from app.domain.signals.models import SignalEvent
from app.domain.signals.scheduling import SchedulingRequest
from app.domain.voice.models import CallRequest
from app.domain_models import (
    AccountContactAssignment,
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


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


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


def test_account_mutations_write_to_local_shared_store_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "upsert_shared_record",
        lambda payload: (_ for _ in ()).throw(
            AssertionError("remote adapter should not be called")
        ),
    )
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "get_shared_record",
        lambda record_id: (_ for _ in ()).throw(
            AssertionError("remote adapter should not be called")
        ),
    )

    with _session() as session:
        created = create_account(
            session,
            workspace_id="ws-shared",
            data=AccountCreate(
                name="Analytical",
                website_url="https://analytical.example.com",
                industry="Education",
                summary="Original summary",
                tags=["priority"],
            ),
        )
        updated = update_account(
            session,
            workspace_id="ws-shared",
            account_id=created.id,
            data=AccountUpdate(
                name="Analytical Engines",
                website_url="https://engines.example.com",
                industry="Research",
                summary="Updated summary",
                tags=["priority", "west"],
            ),
        )
        stored = shared_service.get_shared_account(
            workspace_id="ws-shared",
            account_id=created.id,
            session=session,
        )

    assert created.name == "Analytical"
    assert updated is not None
    assert updated.name == "Analytical Engines"
    assert stored is not None
    assert stored.id == created.id
    assert stored.name == "Analytical Engines"
    assert stored.account_key == "analytical-engines"
    assert stored.website_url == "https://engines.example.com"
    assert stored.industry == "Research"
    assert stored.summary == "Updated summary"
    assert stored.tags == ["priority", "west"]


def test_account_contact_assignment_updates_local_shared_links_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "upsert_shared_record",
        lambda payload: (_ for _ in ()).throw(
            AssertionError("remote adapter should not be called")
        ),
    )
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "get_shared_record",
        lambda record_id: (_ for _ in ()).throw(
            AssertionError("remote adapter should not be called")
        ),
    )

    with _session() as session:
        account = shared_service.upsert_shared_account(
            workspace_id="ws-shared",
            account_id=uuid.uuid4(),
            name="Analytical",
            account_key="analytical",
            session=session,
        )
        contact = shared_service.upsert_shared_contact(
            workspace_id="ws-shared",
            contact_id=uuid.uuid4(),
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
            company="Independent",
            session=session,
        )

        assignment = assign_contacts_to_account(
            session,
            workspace_id="ws-shared",
            account_id=account.id,
            contact_ids=[contact.id],
        )
        linked = shared_service.get_shared_contact(
            workspace_id="ws-shared",
            contact_id=contact.id,
            session=session,
        )
        removal = unassign_contact_from_account(
            session,
            workspace_id="ws-shared",
            account_id=account.id,
            contact_id=contact.id,
        )
        unlinked = shared_service.get_shared_contact(
            workspace_id="ws-shared",
            contact_id=contact.id,
            session=session,
        )

    assert assignment is not None
    assert assignment.assigned_count == 1
    assert linked is not None
    assert linked.account_id == account.id
    assert linked.company == "Analytical"
    assert removal is not None
    assert unlinked is not None
    assert unlinked.account_id is None
    assert unlinked.company == "Analytical"


def test_accounts_route_local_mutations_commit_durably(monkeypatch) -> None:
    monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "upsert_shared_record",
        lambda payload: (_ for _ in ()).throw(
            AssertionError("remote adapter should not be called")
        ),
    )
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "get_shared_record",
        lambda record_id: (_ for _ in ()).throw(
            AssertionError("remote adapter should not be called")
        ),
    )

    engine = _engine()
    with Session(engine) as request_session:
        account = account_routes.create_workspace_account(
            session=request_session,
            workspace_id="ws-shared",
            body=AccountCreate(name="Analytical"),
        )
        contact = shared_service.upsert_shared_contact(
            workspace_id="ws-shared",
            contact_id=uuid.uuid4(),
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
            company="Independent",
            session=request_session,
        )
        updated = account_routes.update_workspace_account(
            account_id=account.id,
            session=request_session,
            workspace_id="ws-shared",
            body=AccountUpdate(name="Analytical Engines", summary="Durable"),
        )
        assigned = account_routes.assign_workspace_account_contacts(
            account_id=account.id,
            session=request_session,
            workspace_id="ws-shared",
            body=AccountContactAssignment(contact_ids=[contact.id]),
        )
        linked = shared_service.get_shared_contact(
            workspace_id="ws-shared",
            contact_id=contact.id,
            session=request_session,
        )
        unassigned = account_routes.unassign_workspace_account_contact(
            account_id=account.id,
            contact_id=contact.id,
            session=request_session,
            workspace_id="ws-shared",
        )

    with Session(engine) as verification_session:
        persisted_account = shared_service.get_shared_account(
            workspace_id="ws-shared",
            account_id=account.id,
            session=verification_session,
        )
        persisted_contact = shared_service.get_shared_contact(
            workspace_id="ws-shared",
            contact_id=contact.id,
            session=verification_session,
        )

    assert updated.name == "Analytical Engines"
    assert assigned.assigned_count == 1
    assert linked is not None
    assert linked.account_id == account.id
    assert unassigned.account_id == account.id
    assert persisted_account is not None
    assert persisted_account.name == "Analytical Engines"
    assert persisted_account.summary == "Durable"
    assert persisted_contact is not None
    assert persisted_contact.account_id is None
    assert persisted_contact.company == "Analytical Engines"


def test_sessionless_local_shared_write_commits_when_service_owns_session(
    monkeypatch,
) -> None:
    monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "upsert_shared_record",
        lambda payload: (_ for _ in ()).throw(
            AssertionError("remote adapter should not be called")
        ),
    )
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "get_shared_record",
        lambda record_id: (_ for _ in ()).throw(
            AssertionError("remote adapter should not be called")
        ),
    )

    engine = _engine()
    monkeypatch.setattr(shared_service, "engine", engine)

    account_id = uuid.uuid4()
    created = shared_service.upsert_shared_account(
        workspace_id="ws-shared",
        account_id=account_id,
        name="Sessionless Account",
        account_key="sessionless-account",
    )

    with Session(engine) as verification_session:
        persisted = shared_service.get_shared_account(
            workspace_id="ws-shared",
            account_id=account_id,
            session=verification_session,
        )

    assert created.id == account_id
    assert persisted is not None
    assert persisted.id == account_id
    assert persisted.name == "Sessionless Account"


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


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("TRUE", True),
        ("false", False),
        ("FALSE", False),
        (None, False),
        ("yes", False),
        (1, False),
        ({"value": True}, False),
    ],
)
def test_shared_contact_consent_is_strict_and_defaults_to_denied(
    raw_value: object,
    expected: bool,
) -> None:
    contact = shared_service.shared_contact_to_public(
        {
            "id": "shared-contact-consent",
            "entityType": "CONTACT",
            "email": "consent@example.com",
            "data": {"workspaceId": "ws-shared", "consentEmail": raw_value},
            "createdAt": "2026-06-30T12:00:00Z",
        },
        workspace_id="ws-shared",
    )

    assert contact.consent_email is expected


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


def test_customer_360_load_accounts_uses_shared_record_service(monkeypatch) -> None:
    account_id = uuid.uuid4()

    monkeypatch.setattr(
        customer_360_service.shared_record_service.ecrm_shared_records,
        "list_shared_records",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("adapter should not be called")),
    )
    monkeypatch.setattr(
        customer_360_service.shared_record_service,
        "list_shared_accounts",
        lambda **kwargs: [
            customer_360_service.Customer360AccountRowPublic(
                id=account_id,
                workspace_id="ws-shared",
                name="Analytical",
                account_key="analytical",
                status="active",
                tags=[],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                contact_count=0,
                last_activity_at=None,
                channel_counts={},
                top_next_action=None,
            )
        ],
    )

    accounts = customer_360_service._load_accounts(
        workspace_id="ws-shared",
        search="ana",
        limit=10,
    )

    assert len(accounts) == 1
    assert accounts[0].id == account_id


def test_accounts_load_account_or_none_uses_shared_record_service(monkeypatch) -> None:
    account_id = uuid.uuid4()

    monkeypatch.setattr(
        accounts_domain.service.shared_record_service.ecrm_shared_records,
        "get_shared_record",
        lambda record_id: (_ for _ in ()).throw(AssertionError("adapter should not be called")),
    )
    monkeypatch.setattr(
        accounts_domain.service.shared_record_service,
        "get_shared_account",
        lambda **kwargs: accounts_domain.service.AccountPublic(
            id=account_id,
            workspace_id="ws-shared",
            name="Analytical",
            account_key="analytical",
            status="active",
            tags=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    )

    loaded = accounts_domain.service._load_account_or_none(
        workspace_id="ws-shared",
        account_id=account_id,
    )

    assert loaded is not None
    assert loaded.id == account_id


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
        assert kwargs == {"workspace_id": "ws-shared", "search": "ada", "limit": 100}
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
            workspace_id="ws-shared",
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            channel="email",
            signal_type="reply",
        ),
        SchedulingRequest(
            workspace_id="ws-shared",
            shared_contact_id=shared_contact_id,
            campaign_id=uuid.uuid4(),
            signal_event_id=uuid.uuid4(),
        ),
        CallRequest(
            workspace_id="ws-shared",
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
