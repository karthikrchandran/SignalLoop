from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.customer_360.service import (
    get_account_profile,
    list_customer_360_accounts,
)
from app.domain_models import (
    Customer360AccountProfilePublic,
    Customer360AccountsPublic,
)

router = APIRouter(
    prefix="/customer-360",
    tags=["customer-360"],
    dependencies=[Depends(require_admin)],
)


@router.get("/accounts", response_model=Customer360AccountsPublic)
def read_customer_360_accounts(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    search: Annotated[str | None, Query(max_length=255)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Customer360AccountsPublic:
    """Return account-first Customer 360 list rows for the active workspace."""
    return list_customer_360_accounts(
        session,
        workspace_id=workspace_id,
        search=search,
        limit=limit,
    )


@router.get("/accounts/{account_id}", response_model=Customer360AccountProfilePublic)
def get_customer_360_account_profile(
    account_id: uuid.UUID,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> Customer360AccountProfilePublic:
    """Return the Account Command Center profile for one workspace-scoped account."""
    profile = get_account_profile(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return profile
