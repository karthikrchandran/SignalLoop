from __future__ import annotations

import uuid
from typing import get_type_hints

from sqlmodel import Session, SQLModel, create_engine

from app.domain.shared_records import service as shared_service
from app.domain.shared_records.repository import PlatformSharedRepository


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_list_shared_contacts_uses_local_repository_when_flag_enabled(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class _Repo:
        def list_contacts(
            self,
            *,
            workspace_id: str,
            search: str | None,
            parent_public_id: uuid.UUID | None,
            limit: int,
        ) -> list[dict[str, object]]:
            captured["workspace_id"] = workspace_id
            captured["search"] = search
            captured["parent_public_id"] = parent_public_id
            captured["limit"] = limit
            return [
                {
                    "id": uuid.uuid4(),
                    "workspace_id": workspace_id,
                    "email": "ada@example.com",
                }
            ]

    monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)
    monkeypatch.setattr(shared_service, "_local_repo", lambda session=None: _Repo())

    rows = shared_service.list_shared_contacts(
        workspace_id="ws-1",
        search="ada",
        parent_id=str(uuid.uuid4()),
        limit=10,
    )

    assert captured["workspace_id"] == "ws-1"
    assert captured["search"] == "ada"
    assert isinstance(captured["parent_public_id"], uuid.UUID)
    assert captured["limit"] == 10
    assert rows[0].email == "ada@example.com"


def test_local_contact_reads_use_repository_and_preserve_emailvoice_public_ids(
    monkeypatch,
) -> None:
    emailvoice_id = uuid.uuid4()

    with _session() as session:
        repo = PlatformSharedRepository(session)
        created = repo.upsert_contact(
            workspace_id="ws-1",
            external_key="emailvoice:contact:ws-1:ada@example.com",
            display_name="Ada Lovelace",
            email="ada@example.com",
            parent_account_id=None,
            source_app="emailvoice",
            source_record_id=str(emailvoice_id),
        )
        session.commit()

        monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)

        rows = shared_service.list_shared_contacts(
            workspace_id="ws-1",
            search="ada",
            limit=10,
            session=session,
        )
        loaded = shared_service.get_shared_contact(
            workspace_id="ws-1",
            contact_id=emailvoice_id,
            session=session,
        )

    assert rows[0].id == emailvoice_id
    assert loaded is not None
    assert loaded.id == emailvoice_id
    assert loaded.email == "ada@example.com"
    assert created.id != emailvoice_id


def test_local_imported_contact_uses_deterministic_public_id_when_emailvoice_id_missing(
    monkeypatch,
) -> None:
    source_record_id = "legacy-contact-1"
    expected_public_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"emailvoice:shared-contact:{source_record_id}",
    )

    with _session() as session:
        repo = PlatformSharedRepository(session)
        repo.upsert_contact(
            workspace_id="ws-1",
            external_key="ecrm:contact:ws-1:ada@example.com",
            display_name="Ada Lovelace",
            email="ada@example.com",
            parent_account_id=None,
            source_app="ecrm",
            source_record_id=source_record_id,
        )
        session.commit()

        monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)

        rows = shared_service.list_shared_contacts(
            workspace_id="ws-1",
            search="ada",
            limit=10,
            session=session,
        )
        loaded = shared_service.get_shared_contact(
            workspace_id="ws-1",
            contact_id=expected_public_id,
            session=session,
        )

    assert rows[0].id == expected_public_id
    assert loaded is not None
    assert loaded.id == expected_public_id


def test_imported_contact_with_emailvoice_legacy_id_preserves_public_id_and_metadata(
    monkeypatch,
) -> None:
    legacy_id = uuid.uuid4()

    with _session() as session:
        repo = PlatformSharedRepository(session)
        contact = repo.upsert_contact(
            workspace_id="ws-1",
            external_key="ecrm:contact:ws-1:ada@example.com",
            display_name="Ada Lovelace",
            email="ada@example.com",
            company_name="Analytical",
            first_name="Ada",
            last_name="Lovelace",
            timezone="America/New_York",
            source_channel="voice",
            tags=["vip"],
            intents=["demo"],
            parent_account_id=None,
            source_app="ecrm",
            source_record_id="contact-1",
        )
        repo._upsert_link(  # noqa: SLF001
            entity_type="CONTACT",
            entity_id=contact.id,
            workspace_id="ws-1",
            source_app="emailvoice",
            source_record_id=str(legacy_id),
        )
        session.commit()

        monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)

        loaded = shared_service.get_shared_contact(
            workspace_id="ws-1",
            contact_id=legacy_id,
            session=session,
        )

    assert loaded is not None
    assert loaded.id == legacy_id
    assert loaded.first_name == "Ada"
    assert loaded.last_name == "Lovelace"
    assert loaded.company == "Analytical"
    assert loaded.timezone == "America/New_York"
    assert loaded.source_channel == "voice"
    assert loaded.tags_json == ["vip"]
    assert loaded.intent_json == ["demo"]


def test_import_command_maps_ecrm_customer_and_contact_into_platform_rows(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fetch_records(
        entity_type: str,
        *,
        _parent_id: str | None = None,
    ) -> list[dict[str, object]]:
        if entity_type == "CUSTOMER":
            return [
                {
                    "id": "customer-1",
                    "externalKey": "ecrm:customer:ws-1:acme",
                    "displayName": "Acme",
                    "data": {"workspaceId": "ws-1"},
                }
            ]
        if entity_type == "CONTACT":
            return [
                {
                    "id": "contact-1",
                    "externalKey": "ecrm:contact:ws-1:ada@example.com",
                    "displayName": "Ada Lovelace",
                    "email": "ada@example.com",
                    "parentId": "customer-1",
                    "data": {"workspaceId": "ws-1"},
                }
            ]
        raise AssertionError(f"unexpected entity_type {entity_type}")

    monkeypatch.setattr(
        "app.scripts.import_ecrm_shared_records.fetch_records",
        fetch_records,
    )

    class _Repo:
        def upsert_account(self, **kwargs):
            calls.append(("ACCOUNT", kwargs["source_record_id"]))
            return type("Account", (), {"id": uuid.uuid4()})()

        def upsert_contact(self, **kwargs):
            calls.append(("CONTACT", kwargs["source_record_id"]))
            return type("Contact", (), {"id": uuid.uuid4()})()

    monkeypatch.setattr(
        "app.scripts.import_ecrm_shared_records.PlatformSharedRepository",
        lambda session: _Repo(),
    )

    from app.scripts.import_ecrm_shared_records import run_import

    summary = run_import(workspace_id="ws-1", dry_run=True)

    assert summary["accounts"] == 1
    assert summary["contacts"] == 1
    assert ("ACCOUNT", "customer-1") in calls
    assert ("CONTACT", "contact-1") in calls


def test_import_command_preserves_emailvoice_legacy_links_and_metadata(monkeypatch) -> None:
    legacy_account_id = uuid.uuid4()
    legacy_contact_id = uuid.uuid4()

    def fetch_records(
        entity_type: str,
        *,
        _parent_id: str | None = None,
    ) -> list[dict[str, object]]:
        if entity_type == "CUSTOMER":
            return [
                {
                    "id": "customer-1",
                    "externalKey": "ecrm:customer:ws-1:acme",
                    "emailVoiceLegacyId": str(legacy_account_id),
                    "displayName": "Acme",
                    "companyName": "Acme",
                    "status": "active",
                    "data": {
                        "workspaceId": "ws-1",
                        "accountKey": "acme",
                        "websiteUrl": "https://acme.example.com",
                        "industry": "Education",
                        "summary": "Strategic account",
                        "tags": ["priority"],
                    },
                }
            ]
        if entity_type == "CONTACT":
            return [
                {
                    "id": "contact-1",
                    "externalKey": "ecrm:contact:ws-1:ada@example.com",
                    "emailVoiceLegacyId": str(legacy_contact_id),
                    "displayName": "Ada Lovelace",
                    "email": "ada@example.com",
                    "phone": "+15551234567",
                    "companyName": "Acme",
                    "status": "active",
                    "parentId": "customer-1",
                    "data": {
                        "workspaceId": "ws-1",
                        "firstName": "Ada",
                        "lastName": "Lovelace",
                        "timezone": "America/New_York",
                        "sourceChannel": "voice",
                        "tags": ["vip"],
                        "intents": ["demo"],
                    },
                }
            ]
        raise AssertionError(f"unexpected entity_type {entity_type}")

    monkeypatch.setattr(
        "app.scripts.import_ecrm_shared_records.fetch_records",
        fetch_records,
    )
    monkeypatch.setattr(shared_service.settings, "USE_LOCAL_SHARED_RECORDS", True)

    from app.scripts.import_ecrm_shared_records import run_import

    with _session() as session:
        summary = run_import(workspace_id="ws-1", dry_run=False, session=session)

        imported_account = shared_service.get_shared_account(
            workspace_id="ws-1",
            account_id=legacy_account_id,
            session=session,
        )
        imported_contact = shared_service.get_shared_contact(
            workspace_id="ws-1",
            contact_id=legacy_contact_id,
            session=session,
        )

    assert summary["accounts"] == 1
    assert summary["contacts"] == 1
    assert imported_account is not None
    assert imported_account.id == legacy_account_id
    assert imported_account.website_url == "https://acme.example.com"
    assert imported_account.industry == "Education"
    assert imported_account.summary == "Strategic account"
    assert imported_account.tags == ["priority"]
    assert imported_contact is not None
    assert imported_contact.id == legacy_contact_id
    assert imported_contact.first_name == "Ada"
    assert imported_contact.last_name == "Lovelace"
    assert imported_contact.company == "Acme"
    assert imported_contact.phone == "+15551234567"
    assert imported_contact.timezone == "America/New_York"
    assert imported_contact.source_channel == "voice"
    assert imported_contact.tags_json == ["vip"]
    assert imported_contact.intent_json == ["demo"]


def test_import_command_skips_records_from_other_workspaces(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fetch_records(
        entity_type: str,
        *,
        _parent_id: str | None = None,
    ) -> list[dict[str, object]]:
        if entity_type == "CUSTOMER":
            return [
                {
                    "id": "customer-1",
                    "externalKey": "ecrm:customer:ws-1:acme",
                    "displayName": "Acme",
                    "data": {"workspaceId": "ws-1"},
                },
                {
                    "id": "customer-2",
                    "externalKey": "ecrm:customer:ws-2:beta",
                    "displayName": "Beta",
                    "data": {"workspaceId": "ws-2"},
                },
            ]
        if entity_type == "CONTACT":
            return [
                {
                    "id": "contact-1",
                    "externalKey": "ecrm:contact:ws-1:ada@example.com",
                    "displayName": "Ada Lovelace",
                    "email": "ada@example.com",
                    "parentId": "customer-1",
                    "data": {"workspaceId": "ws-1"},
                },
                {
                    "id": "contact-2",
                    "externalKey": "ecrm:contact:ws-2:grace@example.com",
                    "displayName": "Grace Hopper",
                    "email": "grace@example.com",
                    "parentId": "customer-2",
                    "data": {"workspaceId": "ws-2"},
                },
            ]
        raise AssertionError(f"unexpected entity_type {entity_type}")

    monkeypatch.setattr(
        "app.scripts.import_ecrm_shared_records.fetch_records",
        fetch_records,
    )

    class _Repo:
        def upsert_account(self, **kwargs):
            calls.append(("ACCOUNT", kwargs["source_record_id"]))
            return type("Account", (), {"id": uuid.uuid4()})()

        def upsert_contact(self, **kwargs):
            calls.append(("CONTACT", kwargs["source_record_id"]))
            return type("Contact", (), {"id": uuid.uuid4()})()

    monkeypatch.setattr(
        "app.scripts.import_ecrm_shared_records.PlatformSharedRepository",
        lambda session: _Repo(),
    )

    from app.scripts.import_ecrm_shared_records import run_import

    summary = run_import(workspace_id="ws-1", dry_run=True)

    assert summary["accounts"] == 1
    assert summary["contacts"] == 1
    assert ("ACCOUNT", "customer-1") in calls
    assert ("CONTACT", "contact-1") in calls
    assert ("ACCOUNT", "customer-2") not in calls
    assert ("CONTACT", "contact-2") not in calls


def test_platform_shared_import_route_delegates_to_service(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.platform_shared.shared_record_service.import_from_ecrm",
        lambda *, workspace_id, dry_run, session=None: {
            "workspace_id": workspace_id,
            "dry_run": dry_run,
            "accounts": 1,
            "contacts": 2,
        },
    )

    from app.api.routes.platform_shared import import_from_ecrm

    result = import_from_ecrm(session=object(), workspace_id="ws-1", dry_run=False)

    assert result["summary"] == {
        "workspace_id": "ws-1",
        "dry_run": False,
        "accounts": 1,
        "contacts": 2,
    }


def test_platform_shared_route_uses_workspace_dependency_annotation() -> None:
    from app.api.request_context import WorkspaceIdDep
    from app.api.routes.platform_shared import import_from_ecrm

    assert get_type_hints(import_from_ecrm, include_extras=True)["workspace_id"] == (
        WorkspaceIdDep
    )
