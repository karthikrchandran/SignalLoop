from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.domain.suite_context.schemas import SuiteContextResponse
from app.domain.suite_context.service import build_suite_context
from app.domain.tenants.capabilities import resolve_suite_context
from app.domain.tenants.models import Tenant

router = APIRouter(prefix="/me", tags=["suite-context"])


@router.get("/suite-context", response_model=SuiteContextResponse)
def read_suite_context(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
) -> SuiteContextResponse:
    if not x_tenant_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Tenant-Key is required")
    tenant = session.exec(select(Tenant).where(Tenant.key == x_tenant_key)).one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    try:
        context = resolve_suite_context(session, user_id=current_user.id, tenant_id=tenant.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Suite access denied") from exc
    return build_suite_context(context=context, tenant=tenant)
