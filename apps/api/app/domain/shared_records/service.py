from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.domain.shared_records.models import (
    PlatformSharedAccount,
    PlatformSharedContact,
)
from app.domain.shared_records.repository import PlatformSharedRepository
from app.domain_models import (
    AccountPublic,
    Contact,
    ContactPublic,
    Customer360AccountProfilePublic,
    Customer360AccountRowPublic,
    Customer360ChannelSummaryPublic,
    Customer360ContactPublic,
)
from app.integrations import ecrm_shared_records
from app.integrations.ecrm_shared_records import EcrmSharedRecordNotFound


@contextmanager
def _local_session(session: Session | None = None):
    managed_session = session or Session(engine)
    owns_session = session is None
    try:
        yield managed_session
    finally:
        if owns_session:
            managed_session.close()


def _local_repo(session: Session | None = None) -> PlatformSharedRepository:
    return PlatformSharedRepository(session or Session(engine))


def _platform_contact_to_public(
    contact: Any,
    *,
    repo: PlatformSharedRepository | None = None,
) -> ContactPublic:
    if isinstance(contact, dict):
        return ContactPublic(
            id=contact["id"],
            workspace_id=str(contact.get("workspace_id", "")),
            account_id=contact.get("account_id"),
            email=str(contact.get("email", "")),
            first_name=contact.get("first_name"),
            last_name=contact.get("last_name"),
            company=contact.get("company"),
            phone=contact.get("phone"),
            timezone=str(contact.get("timezone", "UTC")),
            source_channel=contact.get("source_channel"),
            tags_json=list(contact.get("tags_json", [])),
            intent_json=list(contact.get("intent_json", [])),
            last_seen_at=contact.get("last_seen_at"),
            created_at=contact.get("created_at") or datetime.now(timezone.utc),
        )
    return ContactPublic(
        id=(
            repo._public_id_for_entity(
                workspace_id=contact.workspace_id,
                entity_type="CONTACT",
                entity_id=contact.id,
            )
            if repo is not None
            else _stable_uuid("shared-contact", contact.id)
        ),
        workspace_id=contact.workspace_id,
        account_id=contact.parent_account_id,
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company_name,
        phone=contact.phone,
        timezone=contact.timezone,
        source_channel=contact.source_channel,
        tags_json=list(contact.tags_json or []),
        intent_json=list(contact.intent_json or []),
        last_seen_at=contact.last_seen_at,
        created_at=contact.created_at,
    )


def _platform_account_to_public(
    account: Any,
    *,
    repo: PlatformSharedRepository | None = None,
) -> AccountPublic:
    if isinstance(account, dict):
        return AccountPublic(**account)
    return AccountPublic(
        id=(
            repo._public_id_for_entity(
                workspace_id=account.workspace_id,
                entity_type="ACCOUNT",
                entity_id=account.id,
            )
            if repo is not None
            else _stable_uuid("shared-account", account.id)
        ),
        workspace_id=account.workspace_id,
        name=account.display_name,
        account_key=account.account_key or account.external_key.rsplit(":", 1)[-1],
        website_url=account.website_url,
        industry=account.industry,
        status=account.status,
        summary=account.summary,
        tags=list(account.tags_json or []),
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def _records_from_response(response: dict[str, object]) -> list[dict[str, object]]:
    records = response.get("records", response.get("items", []))
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _record_from_response(response: dict[str, object]) -> dict[str, object]:
    record = response.get("record")
    if isinstance(record, dict):
        return record
    return response


def _stable_uuid(prefix: str, value: object) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"emailvoice:{prefix}:{value}")


def generate_account_key(name: str) -> str:
    """Return a deterministic account key for shared customer records."""
    normalized = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return normalized.strip("-")


def _record_uuid(record: dict[str, object], *, prefix: str) -> uuid.UUID:
    raw_legacy_id = record.get("emailVoiceLegacyId") or record.get(
        "email_voice_legacy_id"
    )
    if isinstance(raw_legacy_id, str):
        try:
            return uuid.UUID(raw_legacy_id)
        except ValueError:
            pass
    return _stable_uuid(prefix, record.get("id", ""))


def _parent_uuid(record: dict[str, object], *, prefix: str) -> uuid.UUID | None:
    raw_parent_id = record.get("parentId") or record.get("parent_id")
    if isinstance(raw_parent_id, str) and raw_parent_id.strip():
        try:
            return uuid.UUID(raw_parent_id)
        except ValueError:
            return _stable_uuid(prefix, raw_parent_id)
    return None


def _timestamp(record: dict[str, object], *keys: str) -> datetime:
    raw_value = next((record.get(key) for key in keys if record.get(key)), None)
    if isinstance(raw_value, str):
        try:
            return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _created_at(record: dict[str, object]) -> datetime:
    return _timestamp(record, "createdAt", "created_at")


def _updated_at(record: dict[str, object]) -> datetime:
    return _timestamp(record, "updatedAt", "updated_at", "createdAt", "created_at")


def _data(record: dict[str, object]) -> dict[str, Any]:
    data = record.get("data")
    return data if isinstance(data, dict) else {}


def shared_contact_to_public(
    record: dict[str, object], *, workspace_id: str
) -> ContactPublic:
    record = _record_from_response(record)
    data = _data(record)
    tags = data.get("tags")
    intents = data.get("intents")
    last_seen_at = _timestamp(data, "lastSeenAt", "last_seen_at")
    return ContactPublic(
        id=_record_uuid(record, prefix="shared-contact"),
        workspace_id=str(data.get("workspaceId") or workspace_id),
        account_id=_parent_uuid(record, prefix="shared-account"),
        email=str(record.get("email") or ""),
        first_name=data.get("firstName")
        if isinstance(data.get("firstName"), str)
        else None,
        last_name=data.get("lastName")
        if isinstance(data.get("lastName"), str)
        else None,
        company=record.get("companyName")
        if isinstance(record.get("companyName"), str)
        else None,
        phone=record.get("phone") if isinstance(record.get("phone"), str) else None,
        timezone=str(data.get("timezone") or "UTC"),
        source_channel=str(data.get("sourceChannel") or "") or None,
        tags_json=[tag for tag in tags if isinstance(tag, str)]
        if isinstance(tags, list)
        else [],
        intent_json=[intent for intent in intents if isinstance(intent, str)]
        if isinstance(intents, list)
        else [],
        last_seen_at=last_seen_at,
        created_at=_created_at(record),
    )


def shared_contact_to_contact(contact: ContactPublic) -> Contact:
    return Contact(
        id=contact.id,
        workspace_id=contact.workspace_id,
        shared_account_id=contact.account_id,
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        phone=contact.phone,
        timezone=contact.timezone,
        source_channel=contact.source_channel,
        tags_json=list(contact.tags_json or []),
        intent_json=list(contact.intent_json or []),
        last_seen_at=contact.last_seen_at,
        created_at=contact.created_at,
    )


def shared_contact_payload(
    *,
    workspace_id: str,
    contact_id: uuid.UUID,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
    company: str | None = None,
    phone: str | None = None,
    timezone: str = "UTC",
    source_channel: str | None = None,
    parent_id: uuid.UUID | None = None,
    tags_json: list[str] | None = None,
    intent_json: list[str] | None = None,
    last_seen_at: datetime | None = None,
) -> dict[str, object]:
    display_name = " ".join(part for part in [first_name, last_name] if part).strip()
    if not display_name:
        display_name = email
    data: dict[str, object] = {
        "workspaceId": workspace_id,
        "firstName": first_name,
        "lastName": last_name,
        "timezone": timezone,
        "sourceChannel": source_channel,
        "tags": list(tags_json or []),
        "intents": list(intent_json or []),
    }
    if last_seen_at is not None:
        data["lastSeenAt"] = last_seen_at.isoformat()
    payload: dict[str, object] = {
        "entityType": "CONTACT",
        "displayName": display_name,
        "status": "active",
        "sourceApp": "emailvoice",
        "emailVoiceLegacyId": str(contact_id),
        "externalKey": f"emailvoice:contact:{workspace_id}:{email.lower()}",
        "email": email,
        "phone": phone,
        "companyName": company,
        "data": data,
    }
    if parent_id is not None:
        payload["parentId"] = str(parent_id)
    return payload


def upsert_shared_contact(
    *,
    workspace_id: str,
    contact_id: uuid.UUID,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
    company: str | None = None,
    phone: str | None = None,
    timezone: str = "UTC",
    source_channel: str | None = None,
    parent_id: uuid.UUID | None = None,
    tags_json: list[str] | None = None,
    intent_json: list[str] | None = None,
    last_seen_at: datetime | None = None,
    session: Session | None = None,
) -> ContactPublic:
    if settings.USE_LOCAL_SHARED_RECORDS:
        with _local_session(session) as local_session:
            repo = _local_repo(local_session)
            existing_contact_id = repo._find_entity_id_by_public_id(
                workspace_id=workspace_id,
                entity_type="CONTACT",
                public_id=contact_id,
            )
            existing_contact = (
                local_session.get(PlatformSharedContact, existing_contact_id)
                if existing_contact_id is not None
                else None
            )
            parent_account_id = None
            if parent_id is not None:
                parent_account_id = repo._find_entity_id_by_public_id(
                    workspace_id=workspace_id,
                    entity_type="ACCOUNT",
                    public_id=parent_id,
                )
            contact = repo.upsert_contact(
                workspace_id=workspace_id,
                external_key=(
                    existing_contact.external_key
                    if existing_contact is not None
                    else f"emailvoice:contact:{workspace_id}:{email.lower()}"
                ),
                display_name=" ".join(
                    part for part in [first_name, last_name] if part and part.strip()
                )
                or email,
                email=email,
                phone=phone,
                company_name=company,
                first_name=first_name,
                last_name=last_name,
                timezone=timezone,
                source_channel=source_channel,
                tags=list(tags_json or []),
                intents=list(intent_json or []),
                last_seen_at=last_seen_at,
                status="active",
                parent_account_id=parent_account_id,
                source_app="emailvoice",
                source_record_id=str(contact_id),
            )
            local_session.flush()
            local_session.refresh(contact)
        return _platform_contact_to_public(contact, repo=repo)

    response = ecrm_shared_records.upsert_shared_record(
        shared_contact_payload(
            workspace_id=workspace_id,
            contact_id=contact_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            company=company,
            phone=phone,
            timezone=timezone,
            source_channel=source_channel,
            parent_id=parent_id,
            tags_json=tags_json,
            intent_json=intent_json,
            last_seen_at=last_seen_at,
        )
    )
    return shared_contact_to_public(response, workspace_id=workspace_id)


def shared_account_payload(
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    name: str,
    account_key: str,
    website_url: str | None = None,
    industry: str | None = None,
    status: str = "active",
    summary: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "entityType": "CUSTOMER",
        "displayName": name,
        "status": status,
        "sourceApp": "emailvoice",
        "emailVoiceLegacyId": str(account_id),
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
    }


def upsert_shared_account(
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    name: str,
    account_key: str,
    website_url: str | None = None,
    industry: str | None = None,
    status: str = "active",
    summary: str | None = None,
    tags: list[str] | None = None,
    session: Session | None = None,
) -> AccountPublic:
    if settings.USE_LOCAL_SHARED_RECORDS:
        with _local_session(session) as local_session:
            repo = _local_repo(local_session)
            existing_account_id = repo._find_entity_id_by_public_id(
                workspace_id=workspace_id,
                entity_type="ACCOUNT",
                public_id=account_id,
            )
            existing_account = (
                local_session.get(PlatformSharedAccount, existing_account_id)
                if existing_account_id is not None
                else None
            )
            account = repo.upsert_account(
                workspace_id=workspace_id,
                external_key=(
                    existing_account.external_key
                    if existing_account is not None
                    else f"emailvoice:account:{workspace_id}:{account_key}"
                ),
                display_name=name,
                status=status,
                account_key=account_key,
                website_url=website_url,
                industry=industry,
                summary=summary,
                tags=list(tags or []),
                source_app="emailvoice",
                source_record_id=str(account_id),
            )
            local_session.flush()
            local_session.refresh(account)
        return _platform_account_to_public(account, repo=repo)

    response = ecrm_shared_records.upsert_shared_record(
        shared_account_payload(
            workspace_id=workspace_id,
            account_id=account_id,
            name=name,
            account_key=account_key,
            website_url=website_url,
            industry=industry,
            status=status,
            summary=summary,
            tags=tags,
        )
    )
    return shared_account_to_public(response, workspace_id=workspace_id)


def list_shared_contacts(
    *,
    workspace_id: str,
    search: str | None = None,
    parent_id: str | None = None,
    limit: int = 50,
    session: Session | None = None,
) -> list[ContactPublic]:
    if settings.USE_LOCAL_SHARED_RECORDS:
        with _local_session(session) as local_session:
            repo = _local_repo(local_session)
            rows = repo.list_contacts(
                workspace_id=workspace_id,
                search=search,
                parent_public_id=uuid.UUID(parent_id) if parent_id else None,
                limit=limit,
            )
        return [_platform_contact_to_public(row, repo=repo) for row in rows]

    request: dict[str, object] = {
        "entity_type": "CONTACT",
        "q": search,
        "status": "active",
        "limit": limit,
    }
    if parent_id is not None:
        request["parent_id"] = parent_id
    response = ecrm_shared_records.list_shared_records(**request)
    contacts = [
        shared_contact_to_public(record, workspace_id=workspace_id)
        for record in _records_from_response(response)
    ]
    return [contact for contact in contacts if contact.workspace_id == workspace_id]


def get_shared_contact(
    *,
    workspace_id: str,
    contact_id: uuid.UUID,
    session: Session | None = None,
) -> ContactPublic | None:
    if settings.USE_LOCAL_SHARED_RECORDS:
        with _local_session(session) as local_session:
            repo = _local_repo(local_session)
            contact = repo.get_contact_by_public_id(
                workspace_id=workspace_id,
                public_id=contact_id,
            )
        if contact is None:
            return None
        return _platform_contact_to_public(contact, repo=repo)

    try:
        response = ecrm_shared_records.get_shared_record(str(contact_id))
    except EcrmSharedRecordNotFound:
        return None
    contact = shared_contact_to_public(response, workspace_id=workspace_id)
    return contact if contact.workspace_id == workspace_id else None


def _account_key(record: dict[str, object]) -> str:
    data = _data(record)
    raw_key = data.get("accountKey")
    if isinstance(raw_key, str) and raw_key.strip():
        return raw_key.strip()
    name = str(record.get("displayName") or record.get("companyName") or "account")
    return "-".join(name.lower().split()) or str(record.get("id") or "account")


def shared_account_to_public(
    record: dict[str, object], *, workspace_id: str
) -> AccountPublic:
    record = _record_from_response(record)
    data = _data(record)
    tags = data.get("tags")
    return AccountPublic(
        id=_record_uuid(record, prefix="shared-account"),
        workspace_id=str(data.get("workspaceId") or workspace_id),
        name=str(record.get("displayName") or record.get("companyName") or ""),
        account_key=_account_key(record),
        website_url=data.get("websiteUrl")
        if isinstance(data.get("websiteUrl"), str)
        else None,
        industry=data.get("industry")
        if isinstance(data.get("industry"), str)
        else None,
        status=str(record.get("status") or "active"),
        summary=data.get("summary") if isinstance(data.get("summary"), str) else None,
        tags=[tag for tag in tags if isinstance(tag, str)]
        if isinstance(tags, list)
        else [],
        created_at=_created_at(record),
        updated_at=_updated_at(record),
    )


def _empty_channel_summary(channel: str, label: str) -> Customer360ChannelSummaryPublic:
    return Customer360ChannelSummaryPublic(
        channel=channel,
        label=label,
        count=0,
        status="empty",
        detail="No local engagement activity yet.",
    )


def _shared_contact_display_name(contact: ContactPublic) -> str:
    name = " ".join(
        part for part in [contact.first_name, contact.last_name] if part
    ).strip()
    return name or contact.email


def shared_contact_to_customer_360(contact: ContactPublic) -> Customer360ContactPublic:
    return Customer360ContactPublic(
        **contact.model_dump(),
        display_name=_shared_contact_display_name(contact),
    )


def _list_customer_records(
    *, search: str | None = None, limit: int = 50
) -> list[dict[str, object]]:
    response = ecrm_shared_records.list_shared_records(
        entity_type="CUSTOMER",
        q=search,
        status="active",
        limit=limit,
    )
    return _records_from_response(response)


def list_shared_accounts(
    *,
    workspace_id: str,
    search: str | None = None,
    limit: int = 50,
    session: Session | None = None,
) -> list[Customer360AccountRowPublic]:
    if settings.USE_LOCAL_SHARED_RECORDS:
        with _local_session(session) as local_session:
            repo = _local_repo(local_session)
            accounts = repo.list_accounts(
                workspace_id=workspace_id,
                search=search,
                limit=limit,
            )
            rows: list[Customer360AccountRowPublic] = []
            for account in accounts:
                contact_count = repo.count_contacts_for_account(
                    workspace_id=workspace_id,
                    account_public_id=account["id"],
                )
                rows.append(
                    Customer360AccountRowPublic(
                        **_platform_account_to_public(account, repo=repo).model_dump(),
                        contact_count=contact_count,
                        last_activity_at=None,
                        channel_counts={},
                        top_next_action=None,
                    )
                )
        return rows

    rows: list[Customer360AccountRowPublic] = []
    for record in _list_customer_records(search=search, limit=limit):
        account = shared_account_to_public(record, workspace_id=workspace_id)
        if account.workspace_id != workspace_id:
            continue
        contacts = list_shared_contacts(
            workspace_id=workspace_id,
            parent_id=str(record.get("id") or ""),
            limit=100,
        )
        rows.append(
            Customer360AccountRowPublic(
                **account.model_dump(),
                contact_count=len(contacts),
                last_activity_at=None,
                channel_counts={},
                top_next_action=None,
            )
        )
    return rows


def get_shared_account(
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    session: Session | None = None,
) -> AccountPublic | None:
    if settings.USE_LOCAL_SHARED_RECORDS:
        with _local_session(session) as local_session:
            repo = _local_repo(local_session)
            account = repo.get_account_by_public_id(
                workspace_id=workspace_id,
                public_id=account_id,
            )
        if account is None:
            return None
        return _platform_account_to_public(account, repo=repo)

    try:
        record = ecrm_shared_records.get_shared_record(str(account_id))
    except EcrmSharedRecordNotFound:
        return None
    account = shared_account_to_public(record, workspace_id=workspace_id)
    return account if account.workspace_id == workspace_id else None


def get_shared_account_profile(
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    session: Session | None = None,
) -> Customer360AccountProfilePublic | None:
    if settings.USE_LOCAL_SHARED_RECORDS:
        with _local_session(session) as local_session:
            repo = _local_repo(local_session)
            account = repo.get_account_by_public_id(
                workspace_id=workspace_id,
                public_id=account_id,
            )
            if account is None:
                return None
            contacts = repo.list_contacts(
                workspace_id=workspace_id,
                search=None,
                parent_public_id=account_id,
                limit=100,
            )
        return Customer360AccountProfilePublic(
            account=_platform_account_to_public(account, repo=repo),
            contacts=[
                shared_contact_to_customer_360(
                    _platform_contact_to_public(contact, repo=repo)
                )
                for contact in contacts
            ],
            channel_summaries={
                "chatbot": _empty_channel_summary("chatbot", "Chatbot"),
                "email": _empty_channel_summary("email", "Email"),
                "voice": _empty_channel_summary("voice", "Voice"),
                "prospecting": _empty_channel_summary("prospecting", "Prospecting"),
            },
            next_best_action=None,
            open_work=[],
            prospecting_brief=None,
            timeline=[],
        )

    for record in _list_customer_records(limit=100):
        account = shared_account_to_public(record, workspace_id=workspace_id)
        if account.id != account_id or account.workspace_id != workspace_id:
            continue
        contacts = list_shared_contacts(
            workspace_id=workspace_id,
            parent_id=str(record.get("id") or ""),
            limit=100,
        )
        return Customer360AccountProfilePublic(
            account=account,
            contacts=[shared_contact_to_customer_360(contact) for contact in contacts],
            channel_summaries={
                "chatbot": _empty_channel_summary("chatbot", "Chatbot"),
                "email": _empty_channel_summary("email", "Email"),
                "voice": _empty_channel_summary("voice", "Voice"),
                "prospecting": _empty_channel_summary("prospecting", "Prospecting"),
            },
            next_best_action=None,
            open_work=[],
            prospecting_brief=None,
            timeline=[],
        )
    return None


def import_from_ecrm(
    *,
    workspace_id: str,
    dry_run: bool = True,
    session: Session | None = None,
) -> dict[str, object]:
    from app.scripts.import_ecrm_shared_records import run_import

    return run_import(workspace_id=workspace_id, dry_run=dry_run, session=session)
