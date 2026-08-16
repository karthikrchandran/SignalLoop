from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.commercial_agents.models import (
    AgentCatalogDefinition,
    AgentDeployment,
    AgentDeploymentStatus,
    AgentPlanEntitlement,
    AgentType,
)
from app.domain.scheduling.models import SchedulingConfirmation
from app.domain.scheduling.providers import (
    CalendarBookingCommand,
    CalendarProviderReceipt,
)
from app.domain.scheduling.schemas import SchedulingRequestCreate
from app.domain.scheduling.service import create_scheduling_request, slot_digest
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    Tenant,
    TenantWorkspaceBinding,
)
from app.domain.workspaces.models import Workspace
from app.domain_models import Campaign, Contact


class ApiCalendarProvider:
    def __init__(self) -> None:
        self.free_busy_calls = 0

    def free_busy(self, **_kwargs):
        self.free_busy_calls += 1
        return []

    def create_event(self, command: CalendarBookingCommand) -> CalendarProviderReceipt:
        return CalendarProviderReceipt(
            command_key=command.command_key,
            provider_event_id=f"event-{command.command_key}",
            provider_receipt_id=f"receipt-{command.command_key}",
            starts_at=command.starts_at,
            ends_at=command.ends_at,
        )

    def lookup_event(
        self, _command_key: str, _credential_secret_ref: str
    ) -> CalendarProviderReceipt | None:
        return None

    def reschedule_event(
        self, command: CalendarBookingCommand
    ) -> CalendarProviderReceipt:
        return self.create_event(command)

    def cancel_event(self, command: CalendarBookingCommand) -> CalendarProviderReceipt:
        return self.create_event(command)


_API_PROVIDER = ApiCalendarProvider()


def calendar_provider_factory() -> ApiCalendarProvider:
    return _API_PROVIDER


def test_admin_configures_offers_and_confirms_without_email_or_voice_dependency(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    _API_PROVIDER.free_busy_calls = 0
    monkeypatch.setenv(
        "CALENDAR_PROVIDER_FACTORY",
        "tests.api.routes.test_calendar_scheduler:calendar_provider_factory",
    )
    tenant, workspace, deployment, request_id = _calendar_context(db)
    base = f"{settings.API_V1_STR}/scheduling/agent/tenants/{tenant.id}"
    meeting = client.post(
        f"{base}/meeting-types",
        headers=_headers(superuser_token_headers, "meeting", workspace.id),
        json={
            "workspace_id": workspace.id,
            "name": "Discovery",
            "duration_minutes": 30,
            "timezone": "UTC",
            "working_hours": {"MONDAY": [["09:00", "17:00"]]},
            "holiday_dates": [],
            "minimum_notice_minutes": 0,
        },
    )
    provider = client.post(
        f"{base}/provider-bindings",
        headers=_headers(superuser_token_headers, "provider", workspace.id),
        json={
            "workspace_id": workspace.id,
            "provider": "CALENDLY",
            "provider_account_ref": "ara-calendar",
            "credential_secret_ref": "secret://calendar/ara",
            "capabilities": ["free_busy.read", "event.create", "event.lookup"],
        },
    )
    next_monday = _next_weekday(date.today(), 0)
    offer_payload = {
        "workspace_id": workspace.id,
        "meeting_type_id": meeting.json()["id"],
        "start_date": next_monday.isoformat(),
        "end_date": next_monday.isoformat(),
        "expires_in_minutes": 60,
        "limit": 3,
    }
    offer_headers = _headers(superuser_token_headers, "offer", workspace.id)
    offer = client.post(
        f"{base}/requests/{request_id}/offers",
        headers=offer_headers,
        json=offer_payload,
    )
    offer_replay = client.post(
        f"{base}/requests/{request_id}/offers",
        headers=offer_headers,
        json=offer_payload,
    )
    selected = slot_digest(offer.json()["slots"][0])
    confirmation_headers = _headers(superuser_token_headers, "confirm", workspace.id)
    confirmation_key = confirmation_headers["Idempotency-Key"]
    confirmation = client.post(
        f"{base}/offers/{offer.json()['id']}/confirm",
        headers=confirmation_headers,
        json={
            "workspace_id": workspace.id,
            "deployment_id": str(deployment.id),
            "binding_id": provider.json()["id"],
            "selected_slot_digest": selected,
            "confirmed_by": "buyer@example.com",
        },
    )

    assert meeting.status_code == 201
    assert provider.status_code == 201
    assert offer.status_code == 201
    assert offer_replay.json() == offer.json()
    assert _API_PROVIDER.free_busy_calls == 1
    assert confirmation.status_code == 201
    assert confirmation.json()["status"] == "PENDING"
    persisted = db.exec(select(SchedulingConfirmation)).one()
    assert persisted.confirmation_key == confirmation_key


def _headers(base: dict[str, str], prefix: str, workspace_id: str) -> dict[str, str]:
    return {
        **base,
        "Idempotency-Key": f"{prefix}-{uuid.uuid4()}",
        "X-Workspace-Id": workspace_id,
    }


def _next_weekday(start: date, weekday: int) -> date:
    days = (weekday - start.weekday()) % 7
    return start + timedelta(days=days or 7)


def _calendar_context(
    db: Session,
) -> tuple[Tenant, Workspace, AgentDeployment, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(key=f"calendar-api-{suffix}", display_name="Calendar API")
    workspace = Workspace(id=f"calendar-{suffix}", name="Calendar API")
    db.add_all([tenant, workspace])
    db.flush()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace.id,
    )
    db.add(installation)
    db.flush()
    db.add(
        TenantWorkspaceBinding(
            tenant_id=tenant.id,
            installation_id=installation.id,
            workspace_id=workspace.id,
        )
    )
    catalog = AgentCatalogDefinition(
        agent_type=AgentType.CALENDAR_SCHEDULER,
        catalog_version=11_000_000 + int(suffix[:5], 16),
        display_name="Calendar Scheduler Agent",
        sellable_outcome="Confirm meetings",
        default_capacity_metric="confirmed_meeting",
        default_capacity_amount=100,
        configuration_schema_version="calendar.v1",
    )
    plan = AgentPlanEntitlement(
        tenant_id=tenant.id,
        installation_id=installation.id,
        plan_code="calendar-test",
        contract_version=f"test-{suffix}",
        purchased_slots=1,
    )
    db.add_all([catalog, plan])
    db.flush()
    deployment = AgentDeployment(
        tenant_id=tenant.id,
        installation_id=installation.id,
        workspace_id=workspace.id,
        catalog_definition_id=catalog.id,
        agent_type=AgentType.CALENDAR_SCHEDULER,
        name=f"Calendar {suffix}",
        status=AgentDeploymentStatus.ACTIVE,
        configuration={},
        configuration_digest="a" * 64,
    )
    contact = Contact(workspace_id=workspace.id, email=f"buyer-{suffix}@example.com")
    campaign = Campaign(
        workspace_id=workspace.id,
        name=f"Calendar campaign {suffix}",
        created_by=uuid.uuid4(),
    )
    db.add_all([deployment, contact, campaign])
    db.commit()
    request = create_scheduling_request(
        db,
        data=SchedulingRequestCreate(contact_id=contact.id, campaign_id=campaign.id),
    )
    return tenant, workspace, deployment, request.id
