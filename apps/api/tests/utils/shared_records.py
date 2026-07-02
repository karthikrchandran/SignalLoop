from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from app.domain.shared_records import service as shared_service
from app.integrations.ecrm_shared_records import EcrmSharedRecordNotFound


class SharedRecordStore:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self.records.clear()

    def get(self, record_id: uuid.UUID | str) -> dict[str, Any] | None:
        return self.records.get(str(record_id))

    def register_account(
        self,
        *,
        workspace_id: str,
        name: str,
        account_key: str,
        account_id: uuid.UUID | None = None,
        website_url: str | None = None,
        industry: str | None = None,
        status: str = "active",
        summary: str | None = None,
        tags: list[str] | None = None,
    ) -> uuid.UUID:
        resolved_id = account_id or uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"emailvoice:account:{workspace_id}:{account_key}",
        )
        now = datetime.now(timezone.utc).isoformat()
        self.records[str(resolved_id)] = {
            "id": str(resolved_id),
            "entityType": "CUSTOMER",
            "displayName": name,
            "status": status,
            "sourceApp": "emailvoice",
            "emailVoiceLegacyId": str(resolved_id),
            "externalKey": f"emailvoice:account:{workspace_id}:{account_key}",
            "companyName": name,
            "data": {
                "workspaceId": workspace_id,
                "accountKey": account_key,
                "websiteUrl": website_url,
                "industry": industry,
                "summary": summary,
                "tags": list(tags or []),
            },
            "createdAt": now,
            "updatedAt": now,
        }
        return resolved_id

    def register_contact(
        self,
        *,
        workspace_id: str,
        email: str,
        contact_id: uuid.UUID | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        company: str | None = None,
        phone: str | None = None,
        timezone_name: str = "UTC",
        source_channel: str | None = None,
        parent_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        intents: list[str] | None = None,
    ) -> uuid.UUID:
        normalized_email = email.lower()
        resolved_id = contact_id or uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"emailvoice:contact:{workspace_id}:{normalized_email}",
        )
        display_name = " ".join(
            part for part in [first_name, last_name] if part
        ).strip() or normalized_email
        now = datetime.now(timezone.utc).isoformat()
        record: dict[str, Any] = {
            "id": str(resolved_id),
            "entityType": "CONTACT",
            "displayName": display_name,
            "status": "active",
            "sourceApp": "emailvoice",
            "emailVoiceLegacyId": str(resolved_id),
            "externalKey": f"emailvoice:contact:{workspace_id}:{normalized_email}",
            "email": normalized_email,
            "phone": phone,
            "companyName": company,
            "data": {
                "workspaceId": workspace_id,
                "firstName": first_name,
                "lastName": last_name,
                "timezone": timezone_name,
                "sourceChannel": source_channel,
                "tags": list(tags or []),
                "intents": list(intents or []),
            },
            "createdAt": now,
            "updatedAt": now,
        }
        if parent_id is not None:
            record["parentId"] = str(parent_id)
        self.records[str(resolved_id)] = record
        return resolved_id


def install_shared_record_mocks(
    monkeypatch: pytest.MonkeyPatch,
) -> SharedRecordStore:
    store = SharedRecordStore()

    def list_shared_records(**kwargs: Any) -> dict[str, Any]:
        entity_type = kwargs.get("entity_type")
        q = str(kwargs.get("q") or "").lower()
        status = kwargs.get("status")
        parent_id = kwargs.get("parent_id")
        records = list(store.records.values())
        if entity_type:
            records = [
                record
                for record in records
                if str(record.get("entityType") or "").upper()
                == str(entity_type).upper()
            ]
        if status is not None:
            records = [
                record
                for record in records
                if str(record.get("status") or "").lower() == str(status).lower()
            ]
        if parent_id is not None:
            records = [
                record
                for record in records
                if str(record.get("parentId") or "") == str(parent_id)
            ]
        if q:
            records = [
                record
                for record in records
                if q
                in " ".join(
                    str(record.get(field) or "")
                    for field in ("displayName", "companyName", "email")
                ).lower()
            ]
        limit = kwargs.get("limit")
        if isinstance(limit, int):
            records = records[:limit]
        return {"records": records}

    def get_shared_record(record_id: str) -> dict[str, Any]:
        record = store.get(record_id)
        if record is None:
            raise EcrmSharedRecordNotFound(record_id)
        return record

    def upsert_shared_record(payload: dict[str, Any]) -> dict[str, Any]:
        record_id = str(payload.get("id") or payload["emailVoiceLegacyId"])
        now = datetime.now(timezone.utc).isoformat()
        existing = store.records.get(record_id)
        record = {
            **payload,
            "id": record_id,
            "createdAt": existing.get("createdAt", now) if existing else now,
            "updatedAt": now,
        }
        store.records[record_id] = record
        return {"record": record, "created": existing is None}

    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "list_shared_records",
        list_shared_records,
    )
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
    return store
