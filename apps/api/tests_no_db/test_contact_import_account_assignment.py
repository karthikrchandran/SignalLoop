from __future__ import annotations

import uuid

from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes.contacts import _contact_public, _upsert_contacts
from app.domain_models import Account, Contact


def _sqlite_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


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

        persisted = session.exec(select(Contact).where(Contact.email == email)).first()
        assert persisted is not None
        assert persisted.account_id is not None
        account = session.get(Account, persisted.account_id)
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
        original_account = Account(
            workspace_id=workspace_id,
            name="Original Co",
            account_key="original-co",
        )
        replacement_account = Account(
            workspace_id=workspace_id,
            name="Replacement Co",
            account_key="replacement-co",
        )
        session.add(original_account)
        session.add(replacement_account)
        session.commit()
        session.refresh(original_account)
        session.refresh(replacement_account)

        contact = Contact(
            workspace_id=workspace_id,
            account_id=original_account.id,
            email=email,
            company=original_account.name,
            timezone="UTC",
        )
        session.add(contact)
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

        persisted = session.exec(select(Contact).where(Contact.email == email)).first()
        assert persisted is not None
        accounts = session.exec(select(Account).where(Account.workspace_id == workspace_id)).all()

    assert created == 0
    assert updated == 1
    assert persisted.account_id == replacement_account.id
    assert persisted.company == replacement_account.name
    assert len(accounts) == 2


def test_upsert_contacts_preserves_account_link_when_import_company_is_blank() -> None:
    workspace_id = f"ws-import-{uuid.uuid4().hex[:8]}"
    email = f"lead-{uuid.uuid4().hex[:8]}@example.com"

    with _sqlite_session() as session:
        account = Account(
            workspace_id=workspace_id,
            name="Analytical",
            account_key="analytical",
        )
        session.add(account)
        session.commit()
        session.refresh(account)

        contact = Contact(
            workspace_id=workspace_id,
            account_id=account.id,
            email=email,
            company=account.name,
            timezone="UTC",
        )
        session.add(contact)
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

        persisted = session.exec(select(Contact).where(Contact.email == email)).first()
        assert persisted is not None
        accounts = session.exec(select(Account).where(Account.workspace_id == workspace_id)).all()

    assert created == 0
    assert updated == 1
    assert persisted.account_id == account.id
    assert persisted.company == account.name
    assert len(accounts) == 1


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
