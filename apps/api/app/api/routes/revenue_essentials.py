from fastapi import APIRouter, Header, HTTPException, status
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.domain.revenue_essentials.schemas import RevenueEssentialsResponse
from app.domain.revenue_essentials.service import build
from app.domain.tenants.capabilities import resolve_suite_context
from app.domain.tenants.models import Tenant

router = APIRouter(prefix="/revenueos", tags=["revenueos-essentials"])


@router.get("/essentials", response_model=RevenueEssentialsResponse)
def read_essentials(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
) -> RevenueEssentialsResponse:
    if not x_tenant_key:
        raise HTTPException(status_code=400, detail="X-Tenant-Key is required")
    tenant = session.exec(select(Tenant).where(Tenant.key == x_tenant_key)).one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    try:
        context = resolve_suite_context(session, user_id=current_user.id, tenant_id=tenant.id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="RevenueOS access denied") from exc
    if "revenueos.essentials.read" not in context.capabilities:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="RevenueOS access denied")
    return build(context)
