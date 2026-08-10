"""Automated followup trigger service — signal → action mapping."""
from __future__ import annotations

import html as html_mod
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.domain.audit.audit_events import append_audit_event
from app.domain.outreach.outbox_service import (
    enqueue_outbox_event,
    mark_outbox_published,
)
from app.domain.runtime_settings import resolve_team_notification_email
from app.domain.shared_records import service as shared_record_service
from app.domain.signals.models import SignalEvent
from app.domain.signals.scheduling import SchedulingRequest
from app.domain.timeline.timeline_service import (
    invalidate_timeline_cache_for_client,
    invalidate_timeline_cache_from_url,
)
from app.domain.voice.models import CallRequest
from app.domain_models import Campaign, Contact, OutboxEvent
from app.infrastructure.providers.base import EmailAdapter
from app.infrastructure.providers.registry import resolve_email_adapter
from app.infrastructure.providers.sendgrid import SendGridAdapter

logger = logging.getLogger(__name__)

# Default trigger rules — signal_type → list of action names
DEFAULT_RULES: dict[str, list[str]] = {
    "email_positive_reply": ["queue_followup_call", "send_demo_email"],
    "scheduling_requested": ["create_scheduling_request", "email_sales_team"],
    "voice_positive_interest": ["send_resource_email"],
}

# In-memory trigger enabled state (MVP — single-process only; not shared across
# multiple worker instances. Move to Redis/DB if horizontal scaling is needed.)
_trigger_enabled: dict[str, bool] = dict.fromkeys(DEFAULT_RULES, True)


def _load_signal_contact(session: Session, signal: SignalEvent) -> Contact | None:
    shared_contact = shared_record_service.get_shared_contact(
        workspace_id=_workspace_for_campaign(session, signal.campaign_id),
        contact_id=signal.shared_contact_id,
    )
    if shared_contact is None:
        return None
    return shared_record_service.shared_contact_to_contact(shared_contact)


async def process_signal(
    session: Session,
    signal: SignalEvent,
    *,
    timeline_cache_redis: Any | None = None,
) -> list[str]:
    """Process a signal event and execute matching trigger actions.

    Returns list of action names that were executed.
    """
    rules = DEFAULT_RULES.get(signal.signal_type, [])
    if not rules:
        return []

    if not _trigger_enabled.get(signal.signal_type, True):
        logger.info("Triggers disabled for %s", signal.signal_type)
        return []

    workspace_id = _workspace_for_campaign(session, signal.campaign_id)
    if workspace_id != signal.workspace_id:
        raise ValueError("signal workspace does not match campaign")
    executed: list[str] = []
    email_adapter: EmailAdapter | None = None
    timeline_cache_dirty = False

    for action in rules:
        try:
            if action == "queue_followup_call":
                timeline_cache_dirty = (
                    _queue_followup_call(session, signal, workspace_id)
                    or timeline_cache_dirty
                )
            elif action == "send_demo_email":
                email_adapter = email_adapter or resolve_email_adapter(
                    session,
                    workspace_id,
                    default_factory=SendGridAdapter,
                )
                await _send_demo_email(email_adapter, session, signal)
            elif action == "create_scheduling_request":
                timeline_cache_dirty = _create_scheduling_request(session, signal) or timeline_cache_dirty
            elif action == "email_sales_team":
                email_adapter = email_adapter or resolve_email_adapter(
                    session,
                    workspace_id,
                    default_factory=SendGridAdapter,
                )
                await _email_sales_team(email_adapter, session, signal)
            elif action == "send_resource_email":
                email_adapter = email_adapter or resolve_email_adapter(
                    session,
                    workspace_id,
                    default_factory=SendGridAdapter,
                )
                await _send_resource_email(email_adapter, session, signal)

            executed.append(action)
            await append_audit_event(
                event_name=f"trigger.{action}",
                workspace_id=workspace_id,
                actor_role="system",
                resource_type="signal",
                resource_id=str(signal.id),
                payload={
                    "signal_id": str(signal.id),
                    "signal_type": signal.signal_type,
                    "contact_id": str(signal.shared_contact_id),
                },
            )
        except Exception:
            logger.exception("Trigger action %s failed for signal %s", action, signal.id)

    session.commit()
    if timeline_cache_dirty:
        if timeline_cache_redis is not None:
            await invalidate_timeline_cache_for_client(
                timeline_cache_redis,
                signal.shared_contact_id,
                signal.campaign_id,
            )
        else:
            await invalidate_timeline_cache_from_url(
                settings.REDIS_URL,
                signal.shared_contact_id,
                signal.campaign_id,
            )
    return executed


def _workspace_for_campaign(session: Session, campaign_id: uuid.UUID) -> str:
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise ValueError("signal campaign not found")
    return campaign.workspace_id


def _signal_action_intent_key(signal_id: uuid.UUID, action: str) -> str:
    return f"signal:{signal_id}:action:{action}"


def _prepare_signal_action_intent(
    session: Session,
    *,
    signal: SignalEvent,
    action: str,
    event_type: str,
    event_data: dict[str, Any],
) -> OutboxEvent | None:
    intent_key = _signal_action_intent_key(signal.id, action)
    existing = session.exec(
        select(OutboxEvent).where(
            OutboxEvent.workspace_id == signal.workspace_id,
            OutboxEvent.idempotency_key == intent_key,
        )
    ).first()
    if existing is not None:
        if existing.published_at is None:
            raise RuntimeError(
                f"Trigger action {action} for signal {signal.id} is already in progress"
            )
        logger.info(
            "Skipping duplicate trigger action %s for signal %s", action, signal.id
        )
        return None

    return enqueue_outbox_event(
        session,
        workspace_id=signal.workspace_id,
        aggregate_id=signal.id,
        aggregate_type="signal",
        event_type=event_type,
        event_data={
            "signal_id": str(signal.id),
            "contact_id": str(signal.shared_contact_id),
            "campaign_id": str(signal.campaign_id),
            "signal_type": signal.signal_type,
            **event_data,
        },
        idempotency_key=intent_key,
    )


def _provider_send_accepted(result: dict[str, Any]) -> bool:
    status_code = int(result.get("status_code") or 0)
    return 200 <= status_code < 300


def _raise_provider_rejected(action: str, result: dict[str, Any]) -> None:
    raise RuntimeError(
        f"Provider rejected trigger action {action}: {result.get('error', 'unknown')}"
    )


def _queue_followup_call(
    session: Session,
    signal: SignalEvent,
    workspace_id: str,
) -> bool:
    """Queue a followup call for a positive email signal."""
    from sqlmodel import select

    from app.domain.voice.models import VoiceScript

    # Find active script for campaign
    script = session.exec(
        select(VoiceScript).where(
            VoiceScript.campaign_id == signal.campaign_id,
            VoiceScript.active == True,  # noqa: E712
        )
    ).first()
    if not script:
        logger.warning("No active voice script for campaign %s", signal.campaign_id)
        return False

    # Schedule for next business hour
    now = datetime.now(timezone.utc)
    scheduled_at = now + timedelta(hours=1)

    call_req = CallRequest(
        workspace_id=workspace_id,
        shared_contact_id=signal.shared_contact_id,
        campaign_id=signal.campaign_id,
        voice_script_id=script.id,
        trigger_reason="positive_email_signal",
        scheduled_at=scheduled_at,
    )
    session.add(call_req)
    return True


async def _send_demo_email(adapter: EmailAdapter, session: Session, signal: SignalEvent) -> None:
    contact = _load_signal_contact(session, signal)
    if not contact:
        return

    intent = _prepare_signal_action_intent(
        session,
        signal=signal,
        action="send_demo_email",
        event_type="trigger.demo_email_send_requested",
        event_data={"to": contact.email},
    )
    if intent is None:
        return

    result = await adapter.send_email(
        to=contact.email,
        subject="Thanks for your interest — here's your demo access",
        body_html="<p>Hi {name},</p><p>Thanks for your interest! Here are some resources to get started:</p><ul><li><a href='#'>Product Demo</a></li><li><a href='#'>Book a Call</a></li></ul>".format(
            name=contact.first_name or "there"
        ),
        body_text=f"Hi {contact.first_name or 'there'}, thanks for your interest! Check out our product demo and book a call.",
        idempotency_key=intent.idempotency_key,
    )
    if not _provider_send_accepted(result):
        _raise_provider_rejected("send_demo_email", result)
    mark_outbox_published(
        session, workspace_id=signal.workspace_id, event_id=intent.id
    )


def _create_scheduling_request(session: Session, signal: SignalEvent) -> bool:
    existing = session.exec(
        select(SchedulingRequest).where(
            SchedulingRequest.workspace_id == signal.workspace_id,
            SchedulingRequest.signal_event_id == signal.id,
        )
    ).first()
    if existing is not None:
        return False
    req = SchedulingRequest(
        workspace_id=signal.workspace_id,
        shared_contact_id=signal.shared_contact_id,
        campaign_id=signal.campaign_id,
        signal_event_id=signal.id,
    )
    session.add(req)
    return True


async def _email_sales_team(adapter: EmailAdapter, session: Session, signal: SignalEvent) -> None:
    contact = _load_signal_contact(session, signal)
    if not contact:
        return

    team_email = resolve_team_notification_email(session, contact.workspace_id)
    if not team_email:
        return

    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    intent = _prepare_signal_action_intent(
        session,
        signal=signal,
        action="email_sales_team",
        event_type="trigger.sales_team_email_requested",
        event_data={"to": team_email},
    )
    if intent is None:
        return

    result = await adapter.send_email(
        to=team_email,
        subject=f"[SCHEDULING] {name} from {contact.company or 'Unknown'} wants to schedule",
        body_html=f"<p><strong>{html_mod.escape(name)}</strong> ({html_mod.escape(contact.email)}) from <strong>{html_mod.escape(contact.company or 'Unknown')}</strong> expressed scheduling interest.</p><p>Please reach out to book a meeting.</p>",
        body_text=f"{name} ({contact.email}) from {contact.company or 'Unknown'} wants to schedule a meeting.",
        idempotency_key=intent.idempotency_key,
    )
    if not _provider_send_accepted(result):
        _raise_provider_rejected("email_sales_team", result)
    mark_outbox_published(
        session, workspace_id=signal.workspace_id, event_id=intent.id
    )


async def _send_resource_email(adapter: EmailAdapter, session: Session, signal: SignalEvent) -> None:
    contact = _load_signal_contact(session, signal)
    if not contact:
        return

    intent = _prepare_signal_action_intent(
        session,
        signal=signal,
        action="send_resource_email",
        event_type="trigger.resource_email_send_requested",
        event_data={"to": contact.email},
    )
    if intent is None:
        return

    result = await adapter.send_email(
        to=contact.email,
        subject="Great speaking with you — here are some resources",
        body_html="<p>Hi {name},</p><p>Thanks for the conversation! Here are some resources that might be helpful:</p><ul><li><a href='#'>Product Overview</a></li><li><a href='#'>Case Studies</a></li></ul><p>Feel free to reach out if you have any questions.</p>".format(
            name=contact.first_name or "there"
        ),
        body_text=f"Hi {contact.first_name or 'there'}, thanks for the conversation! Check out our product overview and case studies.",
        idempotency_key=intent.idempotency_key,
    )
    if not _provider_send_accepted(result):
        _raise_provider_rejected("send_resource_email", result)
    mark_outbox_published(
        session, workspace_id=signal.workspace_id, event_id=intent.id
    )


def get_trigger_rules() -> list[dict]:
    """Return list of trigger rules with enabled status."""
    return [
        {
            "signal_type": signal_type,
            "actions": actions,
            "enabled": _trigger_enabled.get(signal_type, True),
        }
        for signal_type, actions in DEFAULT_RULES.items()
    ]


def set_trigger_enabled(signal_type: str, enabled: bool) -> bool:
    """Enable or disable a trigger rule. Returns True if found."""
    if signal_type in _trigger_enabled:
        _trigger_enabled[signal_type] = enabled
        return True
    return False
