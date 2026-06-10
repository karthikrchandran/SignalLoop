from __future__ import annotations

import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain_models import (
    Account,
    AccountContactAssignmentPublic,
    AccountCreate,
    AccountPublic,
    AccountUpdate,
    Contact,
    get_datetime_utc,
)


class AccountAlreadyExistsError(Exception):
    """Raised when an account key already exists in the workspace."""


class AccountNameRequiredError(Exception):
    """Raised when an account display name cannot produce a usable key."""


class AccountContactNotFoundError(Exception):
    """Raised when a requested contact is not assignable in the workspace."""


def generate_account_key(name: str) -> str:
    """Return a deterministic account key for a display name."""
    normalized = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return normalized.strip("-")


def _find_account_by_key(
    session: Session,
    *,
    workspace_id: str,
    account_key: str,
) -> Account | None:
    return session.exec(
        select(Account).where(
            Account.workspace_id == workspace_id,
            Account.account_key == account_key,
        )
    ).first()


def _clean_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_tag in tags or []:
        tag = raw_tag.strip()
        if not tag or tag in seen:
            continue
        cleaned.append(tag)
        seen.add(tag)
    return cleaned


def find_or_create_account_for_company(
    session: Session,
    *,
    workspace_id: str,
    company_name: str | None,
) -> Account | None:
    """Find or create an account from a contact company name."""
    name = (company_name or "").strip()
    if not name:
        return None
    account_key = generate_account_key(name)
    if not account_key:
        return None

    account = _find_account_by_key(
        session,
        workspace_id=workspace_id,
        account_key=account_key,
    )
    if account is not None:
        return account

    try:
        with session.begin_nested():
            account = Account(
                workspace_id=workspace_id,
                name=name,
                account_key=account_key,
            )
            session.add(account)
            session.flush()
    except IntegrityError:
        account = _find_account_by_key(
            session,
            workspace_id=workspace_id,
            account_key=account_key,
        )
        if account is None:
            raise
    return account


def create_account(
    session: Session,
    *,
    workspace_id: str,
    data: AccountCreate,
) -> Account:
    """Create a workspace-scoped account from an explicit command payload."""
    name = data.name.strip()
    account_key = generate_account_key(name)
    if not account_key:
        raise AccountNameRequiredError
    if _find_account_by_key(
        session,
        workspace_id=workspace_id,
        account_key=account_key,
    ):
        raise AccountAlreadyExistsError

    account = Account(
        workspace_id=workspace_id,
        name=name,
        account_key=account_key,
        website_url=data.website_url,
        industry=data.industry,
        status=data.status.strip() or "active",
        summary=data.summary,
        tags_json=_clean_tags(data.tags),
    )
    try:
        with session.begin_nested():
            session.add(account)
            session.flush()
    except IntegrityError as exc:
        raise AccountAlreadyExistsError from exc
    return account


def update_account(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    data: AccountUpdate,
) -> Account | None:
    """Update a workspace-scoped account and keep linked contact display names aligned."""
    account = session.exec(
        select(Account).where(
            Account.id == account_id,
            Account.workspace_id == workspace_id,
        )
    ).first()
    if account is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    old_name = account.name
    new_name = update_data.pop("name", None)
    if new_name is not None:
        cleaned_name = new_name.strip()
        new_account_key = generate_account_key(cleaned_name)
        if not new_account_key:
            raise AccountNameRequiredError
        existing = _find_account_by_key(
            session,
            workspace_id=workspace_id,
            account_key=new_account_key,
        )
        if existing is not None and existing.id != account.id:
            raise AccountAlreadyExistsError
        account.name = cleaned_name
        account.account_key = new_account_key

    if update_data.get("tags") is not None:
        account.tags_json = _clean_tags(update_data.pop("tags"))
    else:
        update_data.pop("tags", None)

    for field_name, value in update_data.items():
        if value is None and field_name in {
            "website_url",
            "industry",
            "status",
            "summary",
        }:
            continue
        if isinstance(value, str) and field_name in {"industry", "status"}:
            value = value.strip()
        setattr(account, field_name, value)

    if not account.status:
        account.status = "active"
    account.updated_at = get_datetime_utc()

    if account.name != old_name:
        contacts = session.exec(
            select(Contact).where(
                Contact.workspace_id == workspace_id,
                Contact.account_id == account.id,
                Contact.company == old_name,
            )
        ).all()
        for contact in contacts:
            contact.company = account.name

    try:
        session.flush()
    except IntegrityError as exc:
        raise AccountAlreadyExistsError from exc
    return account


def assign_contacts_to_account(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    contact_ids: list[uuid.UUID],
) -> AccountContactAssignmentPublic | None:
    """Link workspace contacts to an account and align their company display name."""
    account = session.exec(
        select(Account).where(
            Account.id == account_id,
            Account.workspace_id == workspace_id,
        )
    ).first()
    if account is None:
        return None

    unique_contact_ids = list(dict.fromkeys(contact_ids))
    contacts = list(
        session.exec(
            select(Contact).where(
                Contact.workspace_id == workspace_id,
                Contact.id.in_(unique_contact_ids),
            )
        ).all()
    )
    found_contact_ids = {contact.id for contact in contacts}
    if any(contact_id not in found_contact_ids for contact_id in unique_contact_ids):
        raise AccountContactNotFoundError

    for contact in contacts:
        contact.account_id = account.id
        contact.company = account.name

    session.flush()
    return AccountContactAssignmentPublic(
        account_id=account.id,
        assigned_count=len(unique_contact_ids),
        contact_ids=unique_contact_ids,
    )


def unassign_contact_from_account(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> AccountContactAssignmentPublic | None:
    """Unlink one workspace contact from an account without changing company text."""
    account = session.exec(
        select(Account).where(
            Account.id == account_id,
            Account.workspace_id == workspace_id,
        )
    ).first()
    if account is None:
        return None

    contact = session.exec(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.workspace_id == workspace_id,
            Contact.account_id == account.id,
        )
    ).first()
    if contact is None:
        raise AccountContactNotFoundError

    contact.account_id = None
    session.flush()
    return AccountContactAssignmentPublic(
        account_id=account.id,
        unassigned_count=1,
        contact_ids=[contact.id],
    )


def account_to_public(account: Account) -> AccountPublic:
    """Map an Account row to the public schema."""
    return AccountPublic(
        id=account.id,
        workspace_id=account.workspace_id,
        name=account.name,
        account_key=account.account_key,
        website_url=account.website_url,
        industry=account.industry,
        status=account.status,
        summary=account.summary,
        tags=account.tags_json or [],
        created_at=account.created_at,
        updated_at=account.updated_at,
    )
