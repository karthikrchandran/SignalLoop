from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.accounts.service import (
    AccountAlreadyExistsError,
    AccountContactNotFoundError,
    AccountNameRequiredError,
    assign_contacts_to_account,
    create_account,
    unassign_contact_from_account,
    update_account,
)
from app.domain_models import (
    AccountContactAssignment,
    AccountContactAssignmentPublic,
    AccountCreate,
    AccountPublic,
    AccountUpdate,
)

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
        created = create_account(session, workspace_id=workspace_id, data=body)
    except AccountNameRequiredError:
        raise HTTPException(status_code=400, detail="Account name is required")
    except AccountAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="Account already exists") from exc
    session.commit()
    return created


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
        updated = update_account(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            data=body,
        )
    except AccountNameRequiredError as exc:
        raise HTTPException(status_code=400, detail="Account name is required") from exc
    except AccountAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="Account already exists") from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Account not found")
    session.commit()
    return updated


@router.post("/{account_id}/contacts", response_model=AccountContactAssignmentPublic)
def assign_workspace_account_contacts(
    *,
    account_id: uuid.UUID,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    body: AccountContactAssignment,
) -> AccountContactAssignmentPublic:
    """Assign contacts to an account in the active workspace."""
    try:
        assigned = assign_contacts_to_account(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            contact_ids=body.contact_ids,
        )
    except AccountContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contact not found") from exc
    if assigned is None:
        raise HTTPException(status_code=404, detail="Account not found")
    session.commit()
    return assigned


@router.delete(
    "/{account_id}/contacts/{contact_id}",
    response_model=AccountContactAssignmentPublic,
)
def unassign_workspace_account_contact(
    *,
    account_id: uuid.UUID,
    contact_id: uuid.UUID,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> AccountContactAssignmentPublic:
    """Unassign a contact from an account in the active workspace."""
    try:
        unassigned = unassign_contact_from_account(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            contact_id=contact_id,
        )
    except AccountContactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Contact not found") from exc
    if unassigned is None:
        raise HTTPException(status_code=404, detail="Account not found")
    session.commit()
    return unassigned
