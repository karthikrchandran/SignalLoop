"""Automated followup trigger service — signal → action mapping."""
from __future__ import annotations

import html as html_mod
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.domain.runtime_settings import resolve_team_notification_email
from app.domain.audit.audit_events import append_audit_event
from app.domain.signals.models import SignalEvent
from app.domain.signals.scheduling import SchedulingRequest
from app.domain.timeline.timeline_service import (
    invalidate_timeline_cache_for_client,
    invalidate_timeline_cache_from_url,
)
from app.domain.voice.models import CallRequest
from app.domain_models import Campaign
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

    executed: list[str] = []
    adapter = SendGridAdapter()
    workspace_id = _workspace_for_campaign(session, signal.campaign_id)
    timeline_cache_dirty = False

    for action in rules:
        try:
            if action == "queue_followup_call":
                timeline_cache_dirty = _queue_followup_call(session, signal) or timeline_cache_dirty
            elif action == "send_demo_email":
                await _send_demo_email(adapter, session, signal)
            elif action == "create_scheduling_request":
                timeline_cache_dirty = _create_scheduling_request(session, signal) or timeline_cache_dirty
            elif action == "email_sales_team":
                await _email_sales_team(adapter, session, signal)
            elif action == "send_resource_email":
                await _send_resource_email(adapter, session, signal)

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
                    "contact_id": str(signal.contact_id),
                },
            )
        except Exception:
            logger.exception("Trigger action %s failed for signal %s", action, signal.id)

    session.commit()
    if timeline_cache_dirty:
        if timeline_cache_redis is not None:
            await invalidate_timeline_cache_for_client(
                timeline_cache_redis,
                signal.contact_id,
                signal.campaign_id,
            )
        else:
            await invalidate_timeline_cache_from_url(
                settings.REDIS_URL,
                signal.contact_id,
                signal.campaign_id,
            )
    return executed


def _workspace_for_campaign(session: Session, campaign_id: uuid.UUID) -> str:
    campaign = session.get(Campaign, campaign_id)
    return campaign.workspace_id if campaign else "system"


def _queue_followup_call(session: Session, signal: SignalEvent) -> bool:
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
        contact_id=signal.contact_id,
        campaign_id=signal.campaign_id,
        voice_script_id=script.id,
        trigger_reason="positive_email_signal",
        scheduled_at=scheduled_at,
    )
    session.add(call_req)
    return True


async def _send_demo_email(
    adapter: SendGridAdapter, session: Session, signal: SignalEvent
) -> None:
    from app.domain_models import Contact

    contact = session.get(Contact, signal.contact_id)
    if not contact:
        return

    await adapter.send_email(
        to=contact.email,
        subject="Thanks for your interest — here's your demo access",
        body_html="<p>Hi {name},</p><p>Thanks for your interest! Here are some resources to get started:</p><ul><li><a href='#'>Product Demo</a></li><li><a href='#'>Book a Call</a></li></ul>".format(
            name=contact.first_name or "there"
        ),
        body_text=f"Hi {contact.first_name or 'there'}, thanks for your interest! Check out our product demo and book a call.",
    )


def _create_scheduling_request(session: Session, signal: SignalEvent) -> bool:
    req = SchedulingRequest(
        contact_id=signal.contact_id,
        campaign_id=signal.campaign_id,
        signal_event_id=signal.id,
    )
    session.add(req)
    return True


async def _email_sales_team(
    adapter: SendGridAdapter, session: Session, signal: SignalEvent
) -> None:
    from app.domain_models import Contact

    contact = session.get(Contact, signal.contact_id)
    if not contact:
        return

    team_email = resolve_team_notification_email(session, contact.workspace_id)
    if not team_email:
        return

    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    await adapter.send_email(
        to=team_email,
        subject=f"[SCHEDULING] {name} from {contact.company or 'Unknown'} wants to schedule",
        body_html=f"<p><strong>{html_mod.escape(name)}</strong> ({html_mod.escape(contact.email)}) from <strong>{html_mod.escape(contact.company or 'Unknown')}</strong> expressed scheduling interest.</p><p>Please reach out to book a meeting.</p>",
        body_text=f"{name} ({contact.email}) from {contact.company or 'Unknown'} wants to schedule a meeting.",
    )


async def _send_resource_email(
    adapter: SendGridAdapter, session: Session, signal: SignalEvent
) -> None:
    from app.domain_models import Contact

    contact = session.get(Contact, signal.contact_id)
    if not contact:
        return

    await adapter.send_email(
        to=contact.email,
        subject="Great speaking with you — here are some resources",
        body_html="<p>Hi {name},</p><p>Thanks for the conversation! Here are some resources that might be helpful:</p><ul><li><a href='#'>Product Overview</a></li><li><a href='#'>Case Studies</a></li></ul><p>Feel free to reach out if you have any questions.</p>".format(
            name=contact.first_name or "there"
        ),
        body_text=f"Hi {contact.first_name or 'there'}, thanks for the conversation! Check out our product overview and case studies.",
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
