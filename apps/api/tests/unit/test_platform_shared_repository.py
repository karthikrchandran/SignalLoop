"""Task 1 repository coverage for platform-owned shared-record storage."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.shared_records.models import (
    PlatformExternalLink,
    PlatformSharedAccount,
    PlatformSharedContact,
)
from app.domain.shared_records.repository import PlatformSharedRepository


def _sqlite_engine(*, foreign_keys: bool = False):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    if foreign_keys:
        event.listen(
            engine,
            "connect",
            lambda dbapi_connection, _record: dbapi_connection.execute(
                "PRAGMA foreign_keys=ON"
            ),
        )
    return engine


def test_upsert_account_reuses_row_for_external_key_and_preserves_links_per_workspace() -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)

        created = repo.upsert_account(
            workspace_id="ws-1",
            external_key="emailvoice:account:ws-1:acme",
            display_name="Acme Learning",
            source_app="emailvoice",
            source_record_id="acct-1",
        )
        updated = repo.upsert_account(
            workspace_id="ws-1",
            external_key="emailvoice:account:ws-1:acme",
            display_name="Acme University",
            source_app="emailvoice",
            source_record_id="acct-1",
        )
        second_workspace = repo.upsert_account(
            workspace_id="ws-2",
            external_key="emailvoice:account:ws-2:beta",
            display_name="Beta Labs",
            source_app="emailvoice",
            source_record_id="acct-1",
        )
        session.commit()

        accounts = session.exec(select(PlatformSharedAccount)).all()
        source_links = session.exec(
            select(PlatformExternalLink).where(
                PlatformExternalLink.entity_type == "ACCOUNT",
                PlatformExternalLink.source_app == "emailvoice",
                PlatformExternalLink.source_record_id == "acct-1",
            )
        ).all()
        ws1_link = session.exec(
            select(PlatformExternalLink).where(
                PlatformExternalLink.entity_type == "ACCOUNT",
                PlatformExternalLink.source_app == "emailvoice",
                PlatformExternalLink.source_record_id == "acct-1",
                PlatformExternalLink.workspace_id == "ws-1",
            )
        ).one()
        ws2_link = session.exec(
            select(PlatformExternalLink).where(
                PlatformExternalLink.entity_type == "ACCOUNT",
                PlatformExternalLink.source_app == "emailvoice",
                PlatformExternalLink.source_record_id == "acct-1",
                PlatformExternalLink.workspace_id == "ws-2",
            )
        ).one()

    assert created.id == updated.id
    assert updated.display_name == "Acme University"
    assert len(accounts) == 2
    assert len(source_links) == 2
    assert ws1_link.entity_id == created.id
    assert ws2_link.entity_id == second_workspace.id


def test_upsert_contact_reuses_row_for_external_key_and_does_not_duplicate_link() -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)

        account = repo.upsert_account(
            workspace_id="ws-1",
            external_key="emailvoice:account:ws-1:acme",
            display_name="Acme Learning",
            source_app="emailvoice",
            source_record_id="acct-1",
        )
        created = repo.upsert_contact(
            workspace_id="ws-1",
            external_key="emailvoice:contact:ws-1:ada@example.com",
            display_name="Ada Lovelace",
            email="ada@example.com",
            parent_account_id=account.id,
            source_app="ecrm",
            source_record_id="contact-1",
        )
        updated = repo.upsert_contact(
            workspace_id="ws-1",
            external_key="emailvoice:contact:ws-1:ada@example.com",
            display_name="Ada Byron",
            email="ada.byron@example.com",
            parent_account_id=account.id,
            source_app="ecrm",
            source_record_id="contact-1",
        )
        session.commit()

        contacts = session.exec(select(PlatformSharedContact)).all()
        source_links = session.exec(
            select(PlatformExternalLink).where(
                PlatformExternalLink.entity_type == "CONTACT",
                PlatformExternalLink.source_app == "ecrm",
                PlatformExternalLink.source_record_id == "contact-1",
                PlatformExternalLink.workspace_id == "ws-1",
            )
        ).all()

    assert created.id == updated.id
    assert updated.display_name == "Ada Byron"
    assert updated.email == "ada.byron@example.com"
    assert len(contacts) == 1
    assert len(source_links) == 1
    assert source_links[0].entity_id == updated.id


def test_upsert_contact_rejects_parent_account_from_different_workspace() -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        ws1_account = repo.upsert_account(
            workspace_id="ws-1",
            external_key="emailvoice:account:ws-1:acme",
            display_name="Acme Learning",
            source_app="emailvoice",
            source_record_id="acct-1",
        )

        with pytest.raises(ValueError, match="same workspace"):
            repo.upsert_contact(
                workspace_id="ws-2",
                external_key="emailvoice:contact:ws-2:ada@example.com",
                display_name="Ada Lovelace",
                email="ada@example.com",
                parent_account_id=ws1_account.id,
                source_app="ecrm",
                source_record_id="contact-1",
            )


def test_upsert_account_rejects_external_key_collision_from_different_workspace() -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        repo.upsert_account(
            workspace_id="ws-1",
            external_key="shared:account:external-1",
            display_name="Acme Learning",
            source_app="emailvoice",
            source_record_id="acct-1",
        )
        session.commit()

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        with pytest.raises(ValueError, match="different workspace"):
            repo.upsert_account(
                workspace_id="ws-2",
                external_key="shared:account:external-1",
                display_name="Beta Labs",
                source_app="emailvoice",
                source_record_id="acct-2",
            )


def test_upsert_contact_rejects_external_key_collision_from_different_workspace() -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        repo.upsert_contact(
            workspace_id="ws-1",
            external_key="shared:contact:external-1",
            display_name="Ada Lovelace",
            email="ada@example.com",
            parent_account_id=None,
            source_app="ecrm",
            source_record_id="contact-1",
        )
        session.commit()

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        with pytest.raises(ValueError, match="different workspace"):
            repo.upsert_contact(
                workspace_id="ws-2",
                external_key="shared:contact:external-1",
                display_name="Grace Hopper",
                email="grace@example.com",
                parent_account_id=None,
                source_app="ecrm",
                source_record_id="contact-2",
            )


def test_upsert_account_converges_when_duplicate_account_insert_races(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as seed_session:
        existing = PlatformSharedAccount(
            workspace_id="ws-1",
            external_key="shared:account:external-1",
            display_name="Existing Acme",
        )
        seed_session.add(existing)
        seed_session.commit()
        existing_id = existing.id

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        original_lookup = repo._get_account_by_external_key
        calls = {"count": 0}

        def stale_lookup(external_key: str) -> PlatformSharedAccount | None:
            calls["count"] += 1
            if calls["count"] == 1:
                return None
            return original_lookup(external_key)

        monkeypatch.setattr(repo, "_get_account_by_external_key", stale_lookup)

        account = repo.upsert_account(
            workspace_id="ws-1",
            external_key="shared:account:external-1",
            display_name="Updated Acme",
            source_app="emailvoice",
            source_record_id="acct-1",
        )
        session.commit()
        account_id = account.id
        account_name = account.display_name

    assert account_id == existing_id
    assert account_name == "Updated Acme"


def test_upsert_account_converges_when_duplicate_link_insert_races(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as seed_session:
        account = PlatformSharedAccount(
            workspace_id="ws-1",
            external_key="shared:account:external-1",
            display_name="Existing Acme",
        )
        seed_session.add(account)
        seed_session.flush()
        seed_session.add(
            PlatformExternalLink(
                workspace_id="ws-1",
                entity_type="ACCOUNT",
                entity_id=account.id,
                source_app="emailvoice",
                source_record_id="acct-1",
            )
        )
        seed_session.commit()

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        original_lookup = repo._get_external_link
        calls = {"count": 0}

        def stale_link_lookup(
            *,
            workspace_id: str,
            entity_type: str,
            source_app: str,
            source_record_id: str,
        ) -> PlatformExternalLink | None:
            calls["count"] += 1
            if calls["count"] == 1:
                return None
            return original_lookup(
                workspace_id=workspace_id,
                entity_type=entity_type,
                source_app=source_app,
                source_record_id=source_record_id,
            )

        monkeypatch.setattr(repo, "_get_external_link", stale_link_lookup)

        updated = repo.upsert_account(
            workspace_id="ws-1",
            external_key="shared:account:external-1",
            display_name="Updated Acme",
            source_app="emailvoice",
            source_record_id="acct-1",
        )
        session.commit()
        updated_id = updated.id
        updated_name = updated.display_name

        links = session.exec(select(PlatformExternalLink)).all()

    assert updated_name == "Updated Acme"
    assert len(links) == 1
    assert links[0].entity_id == updated_id


def test_upsert_account_rejects_source_identity_collision_for_different_entity() -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        first = repo.upsert_account(
            workspace_id="ws-1",
            external_key="shared:account:external-1",
            display_name="Acme Learning",
            source_app="emailvoice",
            source_record_id="acct-1",
        )
        session.commit()
        first_id = first.id

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        with pytest.raises(ValueError, match="already maps to a different entity"):
            repo.upsert_account(
                workspace_id="ws-1",
                external_key="shared:account:external-2",
                display_name="Beta Labs",
                source_app="emailvoice",
                source_record_id="acct-1",
            )

        links = session.exec(select(PlatformExternalLink)).all()

    assert len(links) == 1
    assert links[0].entity_id == first_id


def test_db_rejects_cross_workspace_parent_account_reference() -> None:
    engine = _sqlite_engine(foreign_keys=True)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        account = PlatformSharedAccount(
            workspace_id="ws-1",
            external_key="shared:account:external-1",
            display_name="Acme Learning",
        )
        session.add(account)
        session.commit()

        session.add(
            PlatformSharedContact(
                workspace_id="ws-2",
                external_key="shared:contact:external-1",
                display_name="Ada Lovelace",
                email="ada@example.com",
                parent_account_id=account.id,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_repository_serializes_imported_metadata_and_preserves_emailvoice_legacy_ids() -> None:
    engine = _sqlite_engine()
    SQLModel.metadata.create_all(engine)
    legacy_account_id = uuid.uuid4()
    legacy_contact_id = uuid.uuid4()

    with Session(engine) as session:
        repo = PlatformSharedRepository(session)
        account = repo.upsert_account(
            workspace_id="ws-1",
            external_key="ecrm:customer:ws-1:acme",
            display_name="Acme",
            status="active",
            account_key="acme",
            website_url="https://acme.example.com",
            industry="Education",
            summary="Strategic account",
            tags=["priority"],
            source_app="ecrm",
            source_record_id="customer-1",
        )
        repo._upsert_link(  # noqa: SLF001
            entity_type="ACCOUNT",
            entity_id=account.id,
            workspace_id="ws-1",
            source_app="emailvoice",
            source_record_id=str(legacy_account_id),
        )
        contact = repo.upsert_contact(
            workspace_id="ws-1",
            external_key="ecrm:contact:ws-1:ada@example.com",
            display_name="Ada Lovelace",
            email="ada@example.com",
            company_name="Acme",
            first_name="Ada",
            last_name="Lovelace",
            timezone="America/New_York",
            source_channel="voice",
            tags=["vip"],
            intents=["demo"],
            parent_account_id=account.id,
            source_app="ecrm",
            source_record_id="contact-1",
        )
        repo._upsert_link(  # noqa: SLF001
            entity_type="CONTACT",
            entity_id=contact.id,
            workspace_id="ws-1",
            source_app="emailvoice",
            source_record_id=str(legacy_contact_id),
        )
        session.commit()

        serialized_account = repo.get_account_by_public_id(
            workspace_id="ws-1",
            public_id=legacy_account_id,
        )
        serialized_contact = repo.get_contact_by_public_id(
            workspace_id="ws-1",
            public_id=legacy_contact_id,
        )

    assert serialized_account is not None
    assert serialized_account["id"] == legacy_account_id
    assert serialized_account["website_url"] == "https://acme.example.com"
    assert serialized_account["industry"] == "Education"
    assert serialized_account["summary"] == "Strategic account"
    assert serialized_account["tags"] == ["priority"]
    assert serialized_contact is not None
    assert serialized_contact["id"] == legacy_contact_id
    assert serialized_contact["account_id"] == legacy_account_id
    assert serialized_contact["first_name"] == "Ada"
    assert serialized_contact["last_name"] == "Lovelace"
    assert serialized_contact["company"] == "Acme"
    assert serialized_contact["timezone"] == "America/New_York"
    assert serialized_contact["source_channel"] == "voice"
    assert serialized_contact["tags_json"] == ["vip"]
    assert serialized_contact["intent_json"] == ["demo"]
