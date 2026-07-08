from __future__ import annotations

import uuid

from app.domain.shared_records import service as shared_service


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
            parent_id: str | None,
            limit: int,
        ) -> list[dict[str, object]]:
            captured["workspace_id"] = workspace_id
            captured["search"] = search
            captured["parent_id"] = parent_id
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
        parent_id="acct-1",
        limit=10,
    )

    assert captured == {
        "workspace_id": "ws-1",
        "search": "ada",
        "parent_id": "acct-1",
        "limit": 10,
    }
    assert rows[0].email == "ada@example.com"


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
