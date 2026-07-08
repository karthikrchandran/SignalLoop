from __future__ import annotations

import re
import uuid

from sqlmodel import Session

from app.domain.shared_records import service as shared_record_service
from app.domain_models import (
    AccountContactAssignmentPublic,
    AccountCreate,
    AccountPublic,
    AccountUpdate,
)


class AccountAlreadyExistsError(Exception):
    """Raised when an account key already exists in the workspace."""


class AccountNameRequiredError(Exception):
    """Raised when an account display name cannot produce a usable key."""


class AccountContactNotFoundError(Exception):
    """Raised when a requested contact is not assignable in the workspace."""


def _normalize_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for tag in tags or []:
        normalized = tag.strip()
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def generate_account_key(name: str) -> str:
    """Return a deterministic account key for a display name."""
    normalized = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return normalized.strip("-")


def _account_id(workspace_id: str, account_key: str) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"emailvoice:account:{workspace_id}:{account_key}",
    )


def _load_account_or_none(
    *,
    workspace_id: str,
    account_id: uuid.UUID,
) -> AccountPublic | None:
    return shared_record_service.get_shared_account(
        workspace_id=workspace_id,
        account_id=account_id,
    )


def find_or_create_account_for_company(
    _session: Session,
    *,
    workspace_id: str,
    company_name: str | None,
) -> AccountPublic | None:
    """Find or create an account from a contact company name."""
    name = (company_name or "").strip()
    if not name:
        return None
    account_key = generate_account_key(name)
    if not account_key:
        return None

    account_id = _account_id(workspace_id, account_key)
    existing = _load_account_or_none(workspace_id=workspace_id, account_id=account_id)
    if existing is not None:
        return existing
    return shared_record_service.upsert_shared_account(
        workspace_id=workspace_id,
        account_id=account_id,
        name=name,
        account_key=account_key,
    )


def create_account(
    _session: Session,
    *,
    workspace_id: str,
    data: AccountCreate,
) -> AccountPublic:
    """Create a workspace-scoped account from an explicit command payload."""
    name = data.name.strip()
    account_key = generate_account_key(name)
    if not account_key:
        raise AccountNameRequiredError
    account_id = _account_id(workspace_id, account_key)
    if _load_account_or_none(workspace_id=workspace_id, account_id=account_id):
        raise AccountAlreadyExistsError
    return shared_record_service.upsert_shared_account(
        workspace_id=workspace_id,
        account_id=account_id,
        name=name,
        account_key=account_key,
        website_url=data.website_url,
        industry=data.industry,
        status=data.status.strip() or "active",
        summary=data.summary,
        tags=_normalize_tags(data.tags),
    )


def update_account(
    _session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    data: AccountUpdate,
) -> AccountPublic | None:
    """Update a workspace-scoped account and keep linked contact display names aligned."""
    current = _load_account_or_none(workspace_id=workspace_id, account_id=account_id)
    if current is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    new_name = update_data.pop("name", None)
    old_name = current.name
    if new_name is not None:
        cleaned_name = new_name.strip()
        new_account_key = generate_account_key(cleaned_name)
        if not new_account_key:
            raise AccountNameRequiredError
        new_account_id = _account_id(workspace_id, new_account_key)
        if new_account_id != account_id and _load_account_or_none(
            workspace_id=workspace_id,
            account_id=new_account_id,
        ):
            raise AccountAlreadyExistsError
        current = current.model_copy(
            update={
                "name": cleaned_name,
                "account_key": new_account_key,
            }
        )

    account_key = current.account_key or generate_account_key(current.name)
    if not account_key:
        raise AccountNameRequiredError

    updated = shared_record_service.upsert_shared_account(
        workspace_id=workspace_id,
        account_id=account_id,
        name=current.name,
        account_key=account_key,
        website_url=(
            update_data["website_url"]
            if "website_url" in update_data and update_data["website_url"] is not None
            else current.website_url
        ),
        industry=(
            update_data["industry"]
            if "industry" in update_data and update_data["industry"] is not None
            else current.industry
        ),
        status=(
            update_data["status"].strip()
            if "status" in update_data and update_data["status"] is not None
            else current.status
        ),
        summary=(
            update_data["summary"]
            if "summary" in update_data and update_data["summary"] is not None
            else current.summary
        ),
        tags=(
            _normalize_tags(update_data["tags"])
            if "tags" in update_data and update_data["tags"] is not None
            else current.tags
        ),
    )
    if updated.name != old_name:
        linked_contacts = shared_record_service.list_shared_contacts(
            workspace_id=workspace_id,
            parent_id=str(account_id),
            limit=100,
        )
        for contact in linked_contacts:
            if contact.company != old_name:
                continue
            shared_record_service.upsert_shared_contact(
                workspace_id=workspace_id,
                contact_id=contact.id,
                email=contact.email,
                first_name=contact.first_name,
                last_name=contact.last_name,
                company=updated.name,
                phone=contact.phone,
                timezone=contact.timezone,
                source_channel=contact.source_channel,
                parent_id=updated.id,
                tags_json=list(contact.tags_json or []),
                intent_json=list(contact.intent_json or []),
                last_seen_at=contact.last_seen_at,
            )
    return updated


def assign_contacts_to_account(
    _session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    contact_ids: list[uuid.UUID],
) -> AccountContactAssignmentPublic | None:
    """Link workspace contacts to an account and align their company display name."""
    account = _load_account_or_none(workspace_id=workspace_id, account_id=account_id)
    if account is None:
        return None

    unique_contact_ids = list(dict.fromkeys(contact_ids))
    assigned_count = 0
    for contact_id in unique_contact_ids:
        contact = shared_record_service.get_shared_contact(
            workspace_id=workspace_id,
            contact_id=contact_id,
        )
        if contact is None:
            raise AccountContactNotFoundError
        shared_record_service.upsert_shared_contact(
            workspace_id=workspace_id,
            contact_id=contact.id,
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company=account.name,
            phone=contact.phone,
            timezone=contact.timezone,
            source_channel=contact.source_channel,
            parent_id=account.id,
            tags_json=list(contact.tags_json or []),
            intent_json=list(contact.intent_json or []),
            last_seen_at=contact.last_seen_at,
        )
        assigned_count += 1

    return AccountContactAssignmentPublic(
        account_id=account.id,
        assigned_count=assigned_count,
        contact_ids=unique_contact_ids,
    )


def unassign_contact_from_account(
    _session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> AccountContactAssignmentPublic | None:
    """Unlink one workspace contact from an account without changing company text."""
    account = _load_account_or_none(workspace_id=workspace_id, account_id=account_id)
    if account is None:
        return None

    contact = shared_record_service.get_shared_contact(
        workspace_id=workspace_id,
        contact_id=contact_id,
    )
    if contact is None or contact.account_id != account.id:
        raise AccountContactNotFoundError

    shared_record_service.upsert_shared_contact(
        workspace_id=workspace_id,
        contact_id=contact.id,
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        phone=contact.phone,
        timezone=contact.timezone,
        source_channel=contact.source_channel,
        parent_id=None,
        tags_json=list(contact.tags_json or []),
        intent_json=list(contact.intent_json or []),
        last_seen_at=contact.last_seen_at,
    )
    return AccountContactAssignmentPublic(
        account_id=account.id,
        unassigned_count=1,
        contact_ids=[contact.id],
    )


def account_to_public(account: AccountPublic) -> AccountPublic:
    """Map an account record to the public schema."""
    return account
