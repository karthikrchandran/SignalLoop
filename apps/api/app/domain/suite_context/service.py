from __future__ import annotations

from app.domain.suite_context.schemas import ProductContext, SuiteContextResponse
from app.domain.tenants.capabilities import SuiteContext
from app.domain.tenants.models import ProductCode, Tenant


def build_suite_context(*, context: SuiteContext, tenant: Tenant) -> SuiteContextResponse:
    """Project only the capabilities needed by the employee shell."""
    can_campaign = "signalloop.campaign.manage" in context.capabilities
    can_signal = can_campaign or "signalloop.admin.manage" in context.capabilities
    has_commitarc = ProductCode.COMMIT_ARC.value in context.products
    has_revenue = ProductCode.REVENUE_OS.value in context.products
    essentials = has_commitarc or has_revenue
    return SuiteContextResponse(
        tenant={"key": tenant.key, "display_name": tenant.display_name},
        roles=sorted(role.value for role in context.role_bundles),
        capabilities=sorted(context.capabilities),
        products={
            "commitarc": ProductContext(
                visible=has_commitarc,
                mode="FULL" if has_commitarc else None,
                href="/commitarc" if has_commitarc else None,
            ),
            "revenueos": ProductContext(
                visible=essentials,
                mode="FULL" if "revenueos.admin.manage" in context.capabilities else "ESSENTIALS" if essentials else None,
                href="/" if essentials else None,
                capabilities=sorted(cap for cap in context.capabilities if cap.startswith("revenueos.")),
            ),
            "signalloop": ProductContext(
                visible=can_signal,
                mode="FULL" if can_signal else None,
                href="/campaigns" if can_signal else None,
                capabilities=sorted(cap for cap in context.capabilities if cap.startswith("signalloop.")),
            ),
        },
        default_route="/campaigns" if can_signal else "/",
    )
