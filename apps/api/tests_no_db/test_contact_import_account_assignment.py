from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.api.routes.contacts import _contact_public, _upsert_contacts
from app.domain.shared_records import service as shared_service
from app.domain_models import Contact


def _sqlite_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


@pytest.fixture(autouse=True)
def use_local_shared_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these SQLite tests on the local shared-record implementation."""
    monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)


def _account_id(workspace_id: str, company: str) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"emailvoice:account:{workspace_id}:{shared_service.generate_account_key(company)}",
    )


def _contact_id(workspace_id: str, email: str) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"emailvoice:contact:{workspace_id}:{email.lower()}",
    )


def test_upsert_contacts_assigns_account_from_company() -> None:
    workspace_id = f"ws-import-{uuid.uuid4().hex[:8]}"
    email = f"lead-{uuid.uuid4().hex[:8]}@example.com"

    with _sqlite_session() as session:
        created, updated = _upsert_contacts(
            session,
            workspace_id=workspace_id,
            rows=[
                {
                    "email": email,
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                    "company": "Analytical",
                    "phone": "+15551234567",
                    "timezone": "America/New_York",
                }
            ],
        )
        session.commit()

        persisted = shared_service.get_shared_contact(
            workspace_id=workspace_id,
            contact_id=_contact_id(workspace_id, email),
            session=session,
        )
        assert persisted is not None
        assert persisted.account_id is not None
        account = shared_service.get_shared_account(
            workspace_id=workspace_id,
            account_id=_account_id(workspace_id, "Analytical"),
            session=session,
        )
        assert account is not None
        assert created == 1
        assert updated == 0
        assert account.workspace_id == workspace_id
        assert account.name == "Analytical"
        assert account.account_key == "analytical"
        assert persisted.company == "Analytical"


def test_upsert_contacts_reassigns_existing_contact_to_imported_company_account() -> None:
    workspace_id = f"ws-import-{uuid.uuid4().hex[:8]}"
    email = f"lead-{uuid.uuid4().hex[:8]}@example.com"

    with _sqlite_session() as session:
        original_account = shared_service.upsert_shared_account(
            workspace_id=workspace_id,
            account_id=_account_id(workspace_id, "Original Co"),
            name="Original Co",
            account_key="original-co",
            session=session,
        )
        replacement_account = shared_service.upsert_shared_account(
            workspace_id=workspace_id,
            account_id=_account_id(workspace_id, "Replacement Co"),
            name="Replacement Co",
            account_key="replacement-co",
            session=session,
        )
        shared_service.upsert_shared_contact(
            workspace_id=workspace_id,
            email=email,
            company=original_account.name,
            timezone="UTC",
            contact_id=_contact_id(workspace_id, email),
            parent_id=original_account.id,
            session=session,
        )
        session.commit()

        created, updated = _upsert_contacts(
            session,
            workspace_id=workspace_id,
            rows=[
                {
                    "email": email,
                    "firstName": "",
                    "lastName": "",
                    "company": "Replacement Co",
                    "phone": "",
                    "timezone": "UTC",
                }
            ],
        )
        session.commit()

        persisted = shared_service.get_shared_contact(
            workspace_id=workspace_id,
            contact_id=_contact_id(workspace_id, email),
            session=session,
        )
        assert persisted is not None

        assert created == 0
        assert updated == 1
        assert persisted.account_id == replacement_account.id
        assert persisted.company == replacement_account.name


def test_upsert_contacts_preserves_account_link_when_import_company_is_blank() -> None:
    workspace_id = f"ws-import-{uuid.uuid4().hex[:8]}"
    email = f"lead-{uuid.uuid4().hex[:8]}@example.com"

    with _sqlite_session() as session:
        account = shared_service.upsert_shared_account(
            workspace_id=workspace_id,
            account_id=_account_id(workspace_id, "Analytical"),
            name="Analytical",
            account_key="analytical",
            session=session,
        )
        shared_service.upsert_shared_contact(
            workspace_id=workspace_id,
            email=email,
            company=account.name,
            timezone="UTC",
            contact_id=_contact_id(workspace_id, email),
            parent_id=account.id,
            session=session,
        )
        session.commit()

        created, updated = _upsert_contacts(
            session,
            workspace_id=workspace_id,
            rows=[
                {
                    "email": email,
                    "firstName": "",
                    "lastName": "",
                    "company": "",
                    "phone": "",
                    "timezone": "UTC",
                }
            ],
        )
        session.commit()

        persisted = shared_service.get_shared_contact(
            workspace_id=workspace_id,
            contact_id=_contact_id(workspace_id, email),
            session=session,
        )
        assert persisted is not None

        assert created == 0
        assert updated == 1
        assert persisted.account_id == account.id
        assert persisted.company == account.name


def test_contact_public_includes_account_id() -> None:
    account_id = uuid.uuid4()
    contact = Contact(
        workspace_id="ws-public",
        account_id=account_id,
        email="lead@example.com",
        timezone="UTC",
    )

    public = _contact_public(contact)

    assert public.account_id == account_id
