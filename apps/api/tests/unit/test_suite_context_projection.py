from __future__ import annotations

import uuid

from app.domain.suite_context.service import build_suite_context
from app.domain.tenants.capabilities import SuiteContext
from app.domain.tenants.models import RoleBundle, Tenant


def test_employee_projection_grants_essentials_and_hides_signalloop() -> None:
    tenant = Tenant(id=uuid.uuid4(), key="ara-global", display_name="ARA Global")
    result = build_suite_context(
        context=SuiteContext(
            user_id=uuid.uuid4(),
            tenant_id=tenant.id,
            products=frozenset({"commitarc", "revenueos", "signalloop"}),
            role_bundles=frozenset({RoleBundle.EMPLOYEE}),
            capabilities=frozenset({"revenueos.essentials.read"}),
        ),
        tenant=tenant,
    )
    assert result.products["commitarc"].visible is True
    assert result.products["revenueos"].mode == "ESSENTIALS"
    assert result.products["signalloop"].visible is False
    assert result.default_route == "/"


def test_campaign_operator_gets_signal_loop_navigation() -> None:
    tenant = Tenant(id=uuid.uuid4(), key="ai-consulting", display_name="AI Consulting")
    result = build_suite_context(
        context=SuiteContext(
            user_id=uuid.uuid4(), tenant_id=tenant.id,
            products=frozenset({"commitarc"}),
            role_bundles=frozenset({RoleBundle.ENGAGEMENT_OPERATOR}),
            capabilities=frozenset({"revenueos.essentials.read", "signalloop.campaign.manage"}),
        ), tenant=tenant,
    )
    assert result.products["revenueos"].mode == "ESSENTIALS"
    assert result.products["signalloop"].visible is True
    assert result.default_route == "/campaigns"
