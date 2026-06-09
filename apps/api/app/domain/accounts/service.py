from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain_models import Account, AccountPublic


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
