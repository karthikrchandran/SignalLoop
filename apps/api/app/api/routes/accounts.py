from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.accounts.service import (
    AccountAlreadyExistsError,
    AccountNameRequiredError,
    account_to_public,
    create_account,
    update_account,
)
from app.domain_models import AccountCreate, AccountPublic, AccountUpdate

router = APIRouter(
    prefix="/accounts",
    tags=["accounts"],
    dependencies=[Depends(require_admin)],
)


@router.post("", response_model=AccountPublic)
def create_workspace_account(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    body: AccountCreate,
) -> AccountPublic:
    """Create an account in the active workspace."""
    try:
        account = create_account(session, workspace_id=workspace_id, data=body)
    except AccountNameRequiredError:
        raise HTTPException(status_code=400, detail="Account name is required")
    except AccountAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Account already exists")
    session.commit()
    session.refresh(account)
    return account_to_public(account)


@router.patch("/{account_id}", response_model=AccountPublic)
def update_workspace_account(
    *,
    account_id: uuid.UUID,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    body: AccountUpdate,
) -> AccountPublic:
    """Update account metadata in the active workspace."""
    try:
        account = update_account(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            data=body,
        )
    except AccountNameRequiredError:
        raise HTTPException(status_code=400, detail="Account name is required")
    except AccountAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Account already exists")
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    session.commit()
    session.refresh(account)
    return account_to_public(account)
