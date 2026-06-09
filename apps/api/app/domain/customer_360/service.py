from __future__ import annotations

import uuid
from datetime import datetime
from typing import TypedDict

from sqlalchemy import func
from sqlmodel import Session, select

from app.domain.accounts.service import account_to_public
from app.domain.chatbot.models import (
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotMessage,
)
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailEvent,
    EmailSequence,
    SendRequest,
)
from app.domain.voice.models import CallRequest, CallSession
from app.domain_models import (
    Account,
    Campaign,
    Contact,
    Customer360AccountProfilePublic,
    Customer360AccountRowPublic,
    Customer360AccountsPublic,
    Customer360ChannelSummaryPublic,
    Customer360ContactPublic,
    Customer360NextActionPublic,
    Customer360OpenWorkPublic,
    Customer360ProspectingBriefPublic,
    Customer360TimelineEventPublic,
    ProspectingSnapshot,
)


class _ProfileParts(TypedDict):
    channel_summaries: dict[str, Customer360ChannelSummaryPublic]
    next_best_action: Customer360NextActionPublic | None
    open_work: list[Customer360OpenWorkPublic]
    prospecting_brief: Customer360ProspectingBriefPublic | None
    timeline: list[Customer360TimelineEventPublic]
    last_activity_at: datetime | None


def _contact_name(contact: Contact) -> str:
    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    return name or contact.email


def _contact_public(contact: Contact) -> Customer360ContactPublic:
    return Customer360ContactPublic(
        id=contact.id,
        workspace_id=contact.workspace_id,
        account_id=contact.account_id,
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        phone=contact.phone,
        timezone=contact.timezone,
        created_at=contact.created_at,
        display_name=_contact_name(contact),
    )


def _status_value(value: object) -> str:
    return str(getattr(value, "value", value) or "unknown")


def _latest_message(
    session: Session,
    conversation: ChatbotConversation,
) -> ChatbotMessage | None:
    return session.exec(
        select(ChatbotMessage)
        .where(
            ChatbotMessage.conversation_id == conversation.id,
            ChatbotMessage.workspace_id == conversation.workspace_id,
        )
        .order_by(ChatbotMessage.created_at.desc())
    ).first()


def _snapshot_summary(snapshot: ProspectingSnapshot) -> str:
    value = (snapshot.research_json or {}).get("account_summary")
    if isinstance(value, str) and value.strip():
        return value
    return "Prospecting research is ready."


def _snapshot_next_action(snapshot: ProspectingSnapshot) -> str | None:
    value = (snapshot.research_json or {}).get("suggested_next_action")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _without_final_period(value: str) -> str:
    value = value.strip()
    return value[:-1] if value.endswith(".") else value


def _load_contacts(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
) -> list[Contact]:
    return list(
        session.exec(
            select(Contact)
            .where(Contact.workspace_id == workspace_id, Contact.account_id == account_id)
            .order_by(Contact.created_at.desc())
        ).all(),
    )


def _empty_summary(channel: str, label: str) -> Customer360ChannelSummaryPublic:
    return Customer360ChannelSummaryPublic(
        channel=channel,
        label=label,
        count=0,
        status="empty",
        detail="No activity yet.",
    )


def list_customer_360_accounts(
    session: Session,
    *,
    workspace_id: str,
    search: str | None = None,
    limit: int = 50,
) -> Customer360AccountsPublic:
    stmt = select(Account).where(Account.workspace_id == workspace_id).order_by(Account.name)
    if search and search.strip():
        stmt = stmt.where(Account.name.ilike(f"%{search.strip()}%"))

    accounts = list(session.exec(stmt.limit(limit)).all())
    rows: list[Customer360AccountRowPublic] = []
    for account in accounts:
        contacts = _load_contacts(
            session,
            workspace_id=workspace_id,
            account_id=account.id,
        )
        contact_ids = [contact.id for contact in contacts]
        parts = _build_profile_parts(
            session,
            account=account,
            contacts=contacts,
            contact_ids=contact_ids,
        )
        prospecting_action = (
            parts["prospecting_brief"].suggested_next_action
            if parts["prospecting_brief"] is not None
            else None
        )
        fallback_action = (
            parts["next_best_action"].title
            if parts["next_best_action"] is not None
            else None
        )
        public = account_to_public(account)
        rows.append(
            Customer360AccountRowPublic(
                **public.model_dump(),
                contact_count=len(contacts),
                last_activity_at=parts["last_activity_at"],
                channel_counts={
                    key: value.count
                    for key, value in parts["channel_summaries"].items()
                },
                top_next_action=prospecting_action or fallback_action,
            ),
        )
    return Customer360AccountsPublic(data=rows, count=len(rows))


def get_account_profile(
    session: Session,
    *,
    workspace_id: str,
    account_id: uuid.UUID,
) -> Customer360AccountProfilePublic | None:
    account = session.exec(
        select(Account).where(
            Account.id == account_id,
            Account.workspace_id == workspace_id,
        ),
    ).first()
    if account is None:
        return None

    contacts = _load_contacts(
        session,
        workspace_id=workspace_id,
        account_id=account.id,
    )
    contact_ids = [contact.id for contact in contacts]
    parts = _build_profile_parts(
        session,
        account=account,
        contacts=contacts,
        contact_ids=contact_ids,
    )
    return Customer360AccountProfilePublic(
        account=account_to_public(account),
        contacts=[_contact_public(contact) for contact in contacts],
        channel_summaries=parts["channel_summaries"],
        next_best_action=parts["next_best_action"],
        open_work=parts["open_work"],
        prospecting_brief=parts["prospecting_brief"],
        timeline=parts["timeline"],
    )


def _build_profile_parts(
    session: Session,
    *,
    account: Account,
    contacts: list[Contact],
    contact_ids: list[uuid.UUID],
) -> _ProfileParts:
    if not contact_ids:
        return {
            "channel_summaries": {
                "chatbot": _empty_summary("chatbot", "Chatbot"),
                "email": _empty_summary("email", "Email"),
                "voice": _empty_summary("voice", "Voice"),
                "prospecting": _empty_summary("prospecting", "Prospecting"),
            },
            "next_best_action": None,
            "open_work": [],
            "prospecting_brief": None,
            "timeline": [],
            "last_activity_at": None,
        }

    contact_map = {contact.id: contact for contact in contacts}
    conversations = list(
        session.exec(
            select(ChatbotConversation)
            .where(
                ChatbotConversation.workspace_id == account.workspace_id,
                ChatbotConversation.contact_id.in_(contact_ids),
                ChatbotConversation.deleted_at.is_(None),
            )
            .order_by(ChatbotConversation.last_message_at.desc()),
        ).all(),
    )
    call_rows = list(
        session.exec(
            select(CallRequest, CallSession)
            .join(Campaign, Campaign.id == CallRequest.campaign_id)
            .outerjoin(CallSession, CallRequest.id == CallSession.call_request_id)
            .where(
                CallRequest.contact_id.in_(contact_ids),
                Campaign.workspace_id == account.workspace_id,
            )
            .order_by(CallRequest.created_at.desc()),
        ).all(),
    )
    sequence_states = list(
        session.exec(
            select(ContactSequenceState)
            .join(EmailSequence, ContactSequenceState.sequence_id == EmailSequence.id)
            .join(Campaign, Campaign.id == EmailSequence.campaign_id)
            .where(
                ContactSequenceState.contact_id.in_(contact_ids),
                Campaign.workspace_id == account.workspace_id,
            )
            .order_by(ContactSequenceState.created_at.desc()),
        ).all(),
    )
    snapshots = list(
        session.exec(
            select(ProspectingSnapshot)
            .where(
                ProspectingSnapshot.workspace_id == account.workspace_id,
                ProspectingSnapshot.contact_id.in_(contact_ids),
            )
            .order_by(ProspectingSnapshot.created_at.desc()),
        ).all(),
    )

    send_rows: list[tuple[ContactSequenceState, SendRequest]] = []
    email_events: list[tuple[EmailEvent, uuid.UUID]] = []
    opened_count = 0
    if sequence_states:
        state_ids = [state.id for state in sequence_states]
        state_contact_ids = {state.id: state.contact_id for state in sequence_states}
        send_rows = list(
            session.exec(
                select(ContactSequenceState, SendRequest)
                .join(
                    SendRequest,
                    SendRequest.contact_sequence_state_id == ContactSequenceState.id,
                )
                .where(ContactSequenceState.id.in_(state_ids))
                .order_by(SendRequest.sent_at.desc(), SendRequest.created_at.desc()),
            ).all(),
        )
        if send_rows:
            send_ids = [send_request.id for _state, send_request in send_rows]
            opened_count = int(
                session.exec(
                    select(func.count(EmailEvent.id)).where(
                        EmailEvent.send_request_id.in_(send_ids),
                        EmailEvent.event_type.in_(["opened", "clicked"]),
                    ),
                ).one(),
            )
            events = list(
                session.exec(
                    select(EmailEvent, SendRequest.contact_sequence_state_id)
                    .join(SendRequest, EmailEvent.send_request_id == SendRequest.id)
                    .where(EmailEvent.send_request_id.in_(send_ids))
                    .order_by(EmailEvent.timestamp.desc()),
                ).all(),
            )
            email_events = [
                (event, state_contact_ids[state_id])
                for event, state_id in events
                if state_id in state_contact_ids
            ]

    email_count = len(send_rows) if send_rows else len(sequence_states)
    scheduling_count = sum(
        1
        for _call_request, call_session in call_rows
        if call_session and call_session.scheduling_interest
    )
    escalated_count = sum(1 for conversation in conversations if conversation.escalated)

    channel_summaries = {
        "chatbot": Customer360ChannelSummaryPublic(
            channel="chatbot",
            label="Chatbot",
            count=len(conversations),
            status="active" if conversations else "empty",
            detail=f"{escalated_count} escalated thread(s)",
        ),
        "email": Customer360ChannelSummaryPublic(
            channel="email",
            label="Email",
            count=email_count,
            status="active" if email_count else "empty",
            detail=f"{opened_count} open or click event(s)",
        ),
        "voice": Customer360ChannelSummaryPublic(
            channel="voice",
            label="Voice",
            count=len(call_rows),
            status="active" if call_rows else "empty",
            detail=f"{scheduling_count} follow-up call(s)",
        ),
        "prospecting": Customer360ChannelSummaryPublic(
            channel="prospecting",
            label="Prospecting",
            count=len(snapshots),
            status="ready" if snapshots else "empty",
            detail="Latest brief has drafts." if snapshots else "No research brief yet.",
        ),
    }

    open_work: list[Customer360OpenWorkPublic] = []
    timeline: list[Customer360TimelineEventPublic] = []

    for conversation in conversations:
        contact = (
            contact_map.get(conversation.contact_id)
            if conversation.contact_id is not None
            else None
        )
        message = _latest_message(session, conversation)
        timestamp = conversation.last_message_at or conversation.created_at
        if conversation.escalated or conversation.status in {
            ChatbotConversationStatus.open,
            ChatbotConversationStatus.agent_active,
            ChatbotConversationStatus.bot_paused,
        }:
            open_work.append(
                Customer360OpenWorkPublic(
                    id=f"chatbot-{conversation.id}",
                    source="chatbot",
                    title=(
                        "Chatbot escalation"
                        if conversation.escalated
                        else "Open chatbot thread"
                    ),
                    contact_id=conversation.contact_id,
                    contact_name=_contact_name(contact) if contact else None,
                    status=_status_value(conversation.status),
                    created_at=timestamp,
                ),
            )
        timeline.append(
            Customer360TimelineEventPublic(
                id=f"chatbot-{conversation.id}",
                source="chatbot",
                event_type="chatbot_thread",
                title=(
                    "Chatbot escalation"
                    if conversation.escalated
                    else "Chatbot conversation"
                ),
                detail=conversation.escalation_reason
                or (message.content if message and message.content else "Chatbot activity"),
                contact_id=conversation.contact_id,
                contact_name=_contact_name(contact) if contact else None,
                timestamp=timestamp,
            ),
        )

    for call_request, call_session in call_rows:
        contact = contact_map.get(call_request.contact_id)
        timestamp = call_session.created_at if call_session else call_request.created_at
        if call_session and call_session.scheduling_interest:
            open_work.append(
                Customer360OpenWorkPublic(
                    id=f"voice-{call_request.id}",
                    source="voice",
                    title="Voice follow-up",
                    contact_id=call_request.contact_id,
                    contact_name=_contact_name(contact) if contact else None,
                    status=_status_value(call_session.outcome),
                    created_at=timestamp,
                ),
            )
        timeline.append(
            Customer360TimelineEventPublic(
                id=f"voice-{call_request.id}",
                source="voice",
                event_type="call_session",
                title="Voice call completed" if call_session else "Voice call queued",
                detail=(
                    call_session.transcript
                    if call_session and call_session.transcript
                    else call_request.trigger_reason
                ),
                contact_id=call_request.contact_id,
                contact_name=_contact_name(contact) if contact else None,
                timestamp=timestamp,
            ),
        )

    for state, send_request in send_rows:
        contact = contact_map.get(state.contact_id)
        timestamp = send_request.sent_at or send_request.created_at
        timeline.append(
            Customer360TimelineEventPublic(
                id=f"email-send-{send_request.id}",
                source="email",
                event_type="email_send",
                title="Email sent",
                detail=f"Sequence step {send_request.step_order} {_status_value(send_request.status)}",
                contact_id=state.contact_id,
                contact_name=_contact_name(contact) if contact else None,
                timestamp=timestamp,
            ),
        )

    for event, contact_id in email_events:
        contact = contact_map.get(contact_id)
        timeline.append(
            Customer360TimelineEventPublic(
                id=f"email-event-{event.id}",
                source="email",
                event_type=f"email_{event.event_type}",
                title=f"Email {event.event_type}",
                detail=f"Recipient {event.event_type} an email.",
                contact_id=contact_id,
                contact_name=_contact_name(contact) if contact else None,
                timestamp=event.timestamp,
            ),
        )

    latest_snapshot = snapshots[0] if snapshots else None
    prospecting_brief = None
    if latest_snapshot:
        prospecting_brief = Customer360ProspectingBriefPublic(
            snapshot_id=latest_snapshot.id,
            contact_id=latest_snapshot.contact_id,
            account_summary=_snapshot_summary(latest_snapshot),
            suggested_next_action=_snapshot_next_action(latest_snapshot),
            email_draft_available=bool((latest_snapshot.email_draft or "").strip()),
            voice_opener_available=bool((latest_snapshot.voice_opener or "").strip()),
            created_at=latest_snapshot.created_at,
        )
    for snapshot in snapshots:
        contact = contact_map.get(snapshot.contact_id)
        timeline.append(
            Customer360TimelineEventPublic(
                id=f"prospecting-{snapshot.id}",
                source="prospecting",
                event_type="prospecting_research",
                title="Prospecting research created",
                detail=_snapshot_summary(snapshot),
                contact_id=snapshot.contact_id,
                contact_name=_contact_name(contact) if contact else None,
                timestamp=snapshot.created_at,
            ),
        )

    next_best_action = None
    if open_work:
        first_work = sorted(
            open_work,
            key=lambda item: item.created_at,
            reverse=True,
        )[0]
        if prospecting_brief and prospecting_brief.suggested_next_action:
            title = _without_final_period(prospecting_brief.suggested_next_action)
        else:
            title = first_work.title
        next_best_action = Customer360NextActionPublic(
            title=title,
            reason=f"{account.name} has open {first_work.source} work.",
            source=first_work.source,
            priority="high" if first_work.source in {"chatbot", "voice"} else "medium",
        )
    elif prospecting_brief and prospecting_brief.suggested_next_action:
        next_best_action = Customer360NextActionPublic(
            title=prospecting_brief.suggested_next_action,
            reason="Prospecting research is ready.",
            source="prospecting",
            priority="medium",
        )

    timeline = sorted(timeline, key=lambda event: event.timestamp, reverse=True)[:50]
    last_activity_at = timeline[0].timestamp if timeline else None

    return {
        "channel_summaries": channel_summaries,
        "next_best_action": next_best_action,
        "open_work": sorted(
            open_work,
            key=lambda item: item.created_at,
            reverse=True,
        )[:12],
        "prospecting_brief": prospecting_brief,
        "timeline": timeline,
        "last_activity_at": last_activity_at,
    }
