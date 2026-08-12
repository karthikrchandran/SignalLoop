from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.tenant_admin import BrandingDraftCreate, _authorize
from app.domain.tenants.capabilities import SuiteContext, has_capability
from app.domain.tenants.models import RoleBundle, Tenant


class _Session:
    def __init__(self, tenant: Tenant) -> None:
        self.tenant = tenant

    def get(self, model: object, tenant_id: uuid.UUID) -> Tenant | None:
        return self.tenant if tenant_id == self.tenant.id else None


def test_branding_payload_rejects_non_hex_color() -> None:
    with pytest.raises(ValueError):
        BrandingDraftCreate(
            display_name="ARA Global",
            headline="A useful headline",
            supporting_copy="Approved supporting copy.",
            primary_color="red",
            secondary_color="#ffffff",
        )


def test_platform_admin_can_authorize_without_membership() -> None:
    tenant = Tenant(key="ara-global", display_name="ARA Global")
    user = type("User", (), {"id": uuid.uuid4(), "is_superuser": True})()
    assert (
        _authorize(_Session(tenant), user, tenant.id, "tenant.settings.manage")
        is tenant
    )


def test_member_without_capability_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = Tenant(key="ara-global", display_name="ARA Global")
    user = type("User", (), {"id": uuid.uuid4(), "is_superuser": False})()
    monkeypatch.setattr(
        "app.api.routes.tenant_admin.resolve_suite_context",
        lambda *args, **kwargs: SuiteContext(
            user.id, tenant.id, frozenset({"revenueos"}), frozenset(), frozenset()
        ),
    )
    with pytest.raises(HTTPException) as error:
        _authorize(_Session(tenant), user, tenant.id, "tenant.settings.manage")
    assert error.value.status_code == 403


def test_tenant_owner_permission_explicitly_includes_operational_controls() -> None:
    """A tenant owner may invoke the tenant.settings.manage control boundary."""
    assert has_capability(RoleBundle.TENANT_OWNER, "tenant.settings.manage")
