"""Read-only engagement intelligence assembled from existing workspace data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, SQLModel, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.chatbot.models import (
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotMessage,
)
from app.domain.sequences.models import (
    ContactSequenceState,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
)
from app.domain.voice.models import CallOutcome, CallRequest, CallSession
from app.domain_models import (
    Contact,
    ContactProgression,
    ContactProgressionState,
    NotificationProvider,
    OfferPack,
    ProspectingSnapshot,
    ProviderEventLog,
)


class NextBestActionPublic(SQLModel):
    id: str
    contact_id: uuid.UUID | None = None
    contact_name: str
    company: str | None = None
    channel: str
    priority: str
    score: int
    title: str
    reason: str
    recommended_action: str
    source: str


class UnifiedInboxItemPublic(SQLModel):
    id: str
    source: str
    contact_id: uuid.UUID | None = None
    contact_name: str
    title: str
    summary: str
    priority: str
    status: str
    action_label: str
    next_best_action: str
    created_at: datetime


class JourneyStagePublic(SQLModel):
    id: str
    label: str
    count: int
    description: str


class JourneyEdgePublic(SQLModel):
    from_stage: str
    to_stage: str
    label: str
    count: int


class JourneyCanvasPublic(SQLModel):
    stages: list[JourneyStagePublic]
    edges: list[JourneyEdgePublic]


class KnowledgeGapPublic(SQLModel):
    id: str
    title: str
    source: str
    evidence_count: int
    evidence: list[str]
    recommended_fix: str
    priority: str


class OfferRecommendationPublic(SQLModel):
    id: str
    title: str
    reason: str
    recommended_offer: str
    priority: str


class ExperimentRecommendationPublic(SQLModel):
    id: str
    title: str
    hypothesis: str
    primary_metric: str
    variants: list[str]
    holdout_percent: int
    eligible_count: int
    status: str


class AuditReplayItemPublic(SQLModel):
    id: str
    event_name: str
    resource_type: str | None = None
    resource_id: str | None = None
    actor_role: str | None = None
    summary: str
    created_at: datetime
    payload: dict[str, Any]


class ProviderHealthPublic(SQLModel):
    id: str
    provider: str
    channel: str
    status: str
    success_count: int
    failure_count: int
    last_event_at: datetime | None = None
    recommended_action: str


class PipelineRiskPublic(SQLModel):
    id: str
    contact_id: uuid.UUID
    contact_name: str
    company: str | None = None
    risk_level: str
    risk_score: int
    reasons: list[str]
    recommended_action: str


class EngagementOverviewPublic(SQLModel):
    generated_at: datetime
    next_best_actions: list[NextBestActionPublic]
    unified_inbox: list[UnifiedInboxItemPublic]
    journey: JourneyCanvasPublic
    knowledge_gaps: list[KnowledgeGapPublic]
    offer_recommendations: list[OfferRecommendationPublic]
    experiment_recommendations: list[ExperimentRecommendationPublic]
    audit_replay: list[AuditReplayItemPublic]
    provider_health: list[ProviderHealthPublic]
    pipeline_risks: list[PipelineRiskPublic]


def _contact_name(contact: Contact | None) -> str:
    if contact is None:
        return "Unknown contact"
    name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    return name or contact.email


def _shorten(value: str | None, fallback: str, *, limit: int = 180) -> str:
    text = (value or "").strip()
    if not text:
        return fallback
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}..."


def _status_value(value: object) -> str:
    return str(getattr(value, "value", value) or "unknown")


def _provider_value(value: object) -> str:
    return str(getattr(value, "value", value) or "unknown")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _extract_questions(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        raw = (
            value.get("questions")
            or value.get("items")
            or value.get("unanswered")
            or []
        )
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _latest_message(
    session: Session,
    conversation: ChatbotConversation,
) -> ChatbotMessage | None:
    return session.exec(
        select(ChatbotMessage)
        .where(ChatbotMessage.conversation_id == conversation.id)
        .order_by(ChatbotMessage.created_at.desc())
    ).first()


def _latest_research_action(snapshot: ProspectingSnapshot) -> str:
    research = snapshot.research_json or {}
    action = research.get("suggested_next_action")
    if isinstance(action, str) and action.strip():
        return action.strip()
    return "Use the generated email draft and voice opener."


def _load_workspace_data(
    session: Session,
    workspace_id: str,
) -> tuple[
    dict[uuid.UUID, Contact],
    list[ChatbotConversation],
    list[tuple[CallRequest, CallSession | None, Contact]],
    list[ProspectingSnapshot],
    list[tuple[ContactSequenceState, Contact]],
    list[OfferPack],
    list[AuditEvent],
    list[ProviderEventLog],
    list[tuple[SendRequest, ContactSequenceState, Contact]],
    list[tuple[ContactProgression, Contact]],
]:
    contacts = list(
        session.exec(select(Contact).where(Contact.workspace_id == workspace_id)).all()
    )
    contact_map = {contact.id: contact for contact in contacts}
    conversations = list(
        session.exec(
            select(ChatbotConversation)
            .where(
                ChatbotConversation.workspace_id == workspace_id,
                ChatbotConversation.deleted_at.is_(None),
            )
            .order_by(ChatbotConversation.last_message_at.desc())
            .limit(25)
        ).all()
    )
    calls = list(
        session.exec(
            select(CallRequest, CallSession, Contact)
            .join(Contact, CallRequest.contact_id == Contact.id)
            .outerjoin(CallSession, CallRequest.id == CallSession.call_request_id)
            .where(Contact.workspace_id == workspace_id)
            .order_by(CallRequest.created_at.desc())
            .limit(25)
        ).all()
    )
    snapshots = list(
        session.exec(
            select(ProspectingSnapshot)
            .where(ProspectingSnapshot.workspace_id == workspace_id)
            .order_by(ProspectingSnapshot.created_at.desc())
            .limit(25)
        ).all()
    )
    sequence_states = list(
        session.exec(
            select(ContactSequenceState, Contact)
            .join(Contact, ContactSequenceState.contact_id == Contact.id)
            .where(Contact.workspace_id == workspace_id)
        ).all()
    )
    offer_packs = list(
        session.exec(
            select(OfferPack)
            .where(OfferPack.workspace_id == workspace_id)
            .order_by(OfferPack.created_at.desc())
            .limit(5)
        ).all()
    )
    audit_events = list(
        session.exec(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(25)
        ).all()
    )
    provider_events = list(
        session.exec(
            select(ProviderEventLog)
            .where(ProviderEventLog.workspace_id == workspace_id)
            .order_by(ProviderEventLog.received_at.desc())
            .limit(50)
        ).all()
    )
    send_requests = list(
        session.exec(
            select(SendRequest, ContactSequenceState, Contact)
            .join(
                ContactSequenceState,
                SendRequest.contact_sequence_state_id == ContactSequenceState.id,
            )
            .join(Contact, ContactSequenceState.contact_id == Contact.id)
            .where(Contact.workspace_id == workspace_id)
            .order_by(SendRequest.created_at.desc())
            .limit(50)
        ).all()
    )
    progressions = list(
        session.exec(
            select(ContactProgression, Contact)
            .join(Contact, ContactProgression.contact_id == Contact.id)
            .where(Contact.workspace_id == workspace_id)
        ).all()
    )
    return (
        contact_map,
        conversations,
        calls,
        snapshots,
        sequence_states,
        offer_packs,
        audit_events,
        provider_events,
        send_requests,
        progressions,
    )


def _build_next_best_actions(
    *,
    contact_map: dict[uuid.UUID, Contact],
    conversations: list[ChatbotConversation],
    calls: list[tuple[CallRequest, CallSession | None, Contact]],
    snapshots: list[ProspectingSnapshot],
    sequence_states: list[tuple[ContactSequenceState, Contact]],
    session: Session,
) -> list[NextBestActionPublic]:
    active_sequence_contact_ids = {
        contact.id
        for state, contact in sequence_states
        if state.status == SequenceStatus.active
    }
    actions: list[NextBestActionPublic] = []

    for call_request, call_session, contact in calls:
        if not call_session or not call_session.scheduling_interest:
            continue
        questions = _extract_questions(call_session.unanswered_questions)
        reason = questions[0] if questions else call_session.transcript
        actions.append(
            NextBestActionPublic(
                id=f"nba-voice-{call_request.id}",
                contact_id=contact.id,
                contact_name=_contact_name(contact),
                company=contact.company,
                channel="voice",
                priority="high",
                score=95,
                title="Book meeting from voice call",
                reason=_shorten(
                    reason, "Answered voice call needs scheduling follow-up."
                ),
                recommended_action="Book the requested meeting time.",
                source="voice",
            )
        )

    unresolved_statuses = {
        ChatbotConversationStatus.open,
        ChatbotConversationStatus.escalated,
        ChatbotConversationStatus.agent_active,
        ChatbotConversationStatus.bot_paused,
    }
    for conversation in conversations:
        if (
            conversation.status not in unresolved_statuses
            and not conversation.escalated
        ):
            continue
        contact = (
            contact_map.get(conversation.contact_id)
            if conversation.contact_id
            else None
        )
        message = _latest_message(session, conversation)
        reason_text = conversation.escalation_reason or (
            message.content if message else None
        )
        actions.append(
            NextBestActionPublic(
                id=f"nba-chatbot-{conversation.id}",
                contact_id=conversation.contact_id,
                contact_name=_contact_name(contact),
                company=contact.company if contact else None,
                channel="chatbot",
                priority="high" if conversation.escalated else "medium",
                score=90 if conversation.escalated else 75,
                title="Reply to escalated chatbot thread"
                if conversation.escalated
                else "Review open chatbot thread",
                reason=_shorten(
                    reason_text,
                    "Open chatbot thread needs human review.",
                ),
                recommended_action="Open the thread and answer the buyer's question.",
                source="chatbot",
            )
        )

    for snapshot in snapshots:
        contact = contact_map.get(snapshot.contact_id)
        if contact is None or contact.id in active_sequence_contact_ids:
            continue
        actions.append(
            NextBestActionPublic(
                id=f"nba-prospecting-{snapshot.id}",
                contact_id=contact.id,
                contact_name=_contact_name(contact),
                company=contact.company,
                channel="email",
                priority="medium",
                score=75,
                title="Enroll researched prospect in sequence",
                reason=_shorten(
                    _latest_research_action(snapshot), "Prospecting research is ready."
                ),
                recommended_action="Add the researched prospect to a campaign sequence.",
                source="prospecting",
            )
        )

    return sorted(actions, key=lambda action: action.score, reverse=True)[:8]


def _build_unified_inbox(
    *,
    contact_map: dict[uuid.UUID, Contact],
    conversations: list[ChatbotConversation],
    calls: list[tuple[CallRequest, CallSession | None, Contact]],
    snapshots: list[ProspectingSnapshot],
    session: Session,
) -> list[UnifiedInboxItemPublic]:
    items: list[UnifiedInboxItemPublic] = []
    unresolved_statuses = {
        ChatbotConversationStatus.open,
        ChatbotConversationStatus.escalated,
        ChatbotConversationStatus.agent_active,
        ChatbotConversationStatus.bot_paused,
    }
    for conversation in conversations:
        if (
            conversation.status not in unresolved_statuses
            and not conversation.escalated
        ):
            continue
        contact = (
            contact_map.get(conversation.contact_id)
            if conversation.contact_id
            else None
        )
        message = _latest_message(session, conversation)
        items.append(
            UnifiedInboxItemPublic(
                id=f"chatbot-{conversation.id}",
                source="chatbot",
                contact_id=conversation.contact_id,
                contact_name=_contact_name(contact),
                title="Chatbot escalation"
                if conversation.escalated
                else "Open chatbot thread",
                summary=_shorten(
                    message.content if message else None, "No message content."
                ),
                priority="high" if conversation.escalated else "medium",
                status=_status_value(conversation.status),
                action_label="Reply in inbox",
                next_best_action="Open the thread and answer the buyer's question.",
                created_at=conversation.last_message_at or conversation.created_at,
            )
        )

    for call_request, call_session, contact in calls:
        if call_session is None:
            continue
        questions = _extract_questions(call_session.unanswered_questions)
        if not call_session.scheduling_interest and not questions:
            continue
        items.append(
            UnifiedInboxItemPublic(
                id=f"voice-{call_request.id}",
                source="voice",
                contact_id=contact.id,
                contact_name=_contact_name(contact),
                title="Voice follow-up",
                summary=_shorten(
                    call_session.transcript or (questions[0] if questions else None),
                    "Voice call needs follow-up.",
                ),
                priority="high" if call_session.scheduling_interest else "medium",
                status=_status_value(call_session.outcome),
                action_label="Schedule meeting"
                if call_session.scheduling_interest
                else "Send follow-up",
                next_best_action="Book the requested meeting time."
                if call_session.scheduling_interest
                else "Send a follow-up that addresses the open question.",
                created_at=call_session.created_at,
            )
        )

    for snapshot in snapshots[:5]:
        contact = contact_map.get(snapshot.contact_id)
        if contact is None:
            continue
        items.append(
            UnifiedInboxItemPublic(
                id=f"prospecting-{snapshot.id}",
                source="prospecting",
                contact_id=contact.id,
                contact_name=_contact_name(contact),
                title="Prospecting research ready",
                summary=_shorten(
                    _latest_research_action(snapshot), "Research is ready."
                ),
                priority="medium",
                status="ready",
                action_label="Add to outreach",
                next_best_action="Review the draft and enroll the prospect.",
                created_at=snapshot.created_at,
            )
        )

    return sorted(items, key=lambda item: item.created_at, reverse=True)[:12]


def _build_journey(
    *,
    conversations: list[ChatbotConversation],
    calls: list[tuple[CallRequest, CallSession | None, Contact]],
    snapshots: list[ProspectingSnapshot],
    sequence_states: list[tuple[ContactSequenceState, Contact]],
) -> JourneyCanvasPublic:
    chatbot_contacts = {
        conversation.contact_id
        for conversation in conversations
        if conversation.contact_id is not None
        and (conversation.escalated or conversation.lead_capture_intent)
    }
    researched_contacts = {snapshot.contact_id for snapshot in snapshots}
    enrolled_contacts = {
        contact.id
        for state, contact in sequence_states
        if state.status == SequenceStatus.active
    }
    voice_contacts = {contact.id for _, _, contact in calls}
    handoff_contacts = set(chatbot_contacts)
    handoff_contacts.update(
        contact.id
        for _, call_session, contact in calls
        if call_session and call_session.scheduling_interest
    )

    stages = [
        JourneyStagePublic(
            id="chatbot_capture",
            label="Chatbot capture",
            count=len(chatbot_contacts),
            description="Leads or escalations captured by Messaging Hub.",
        ),
        JourneyStagePublic(
            id="prospecting_research",
            label="Prospecting research",
            count=len(researched_contacts),
            description="Contacts with AI research and outreach drafts.",
        ),
        JourneyStagePublic(
            id="sequence_enrollment",
            label="Sequence enrollment",
            count=len(enrolled_contacts),
            description="Contacts actively enrolled in outreach sequences.",
        ),
        JourneyStagePublic(
            id="voice_follow_up",
            label="Voice follow-up",
            count=len(voice_contacts),
            description="Contacts with voice call activity.",
        ),
        JourneyStagePublic(
            id="sales_handoff",
            label="Sales handoff",
            count=len(handoff_contacts),
            description="Contacts needing human follow-up.",
        ),
    ]
    return JourneyCanvasPublic(
        stages=stages,
        edges=[
            JourneyEdgePublic(
                from_stage="chatbot_capture",
                to_stage="prospecting_research",
                label="Research captured lead",
                count=len(chatbot_contacts & researched_contacts),
            ),
            JourneyEdgePublic(
                from_stage="prospecting_research",
                to_stage="sequence_enrollment",
                label="Enroll in outreach",
                count=len(researched_contacts & enrolled_contacts),
            ),
            JourneyEdgePublic(
                from_stage="sequence_enrollment",
                to_stage="voice_follow_up",
                label="Voice assist",
                count=len(enrolled_contacts & voice_contacts),
            ),
            JourneyEdgePublic(
                from_stage="voice_follow_up",
                to_stage="sales_handoff",
                label="Human follow-up",
                count=len(voice_contacts & handoff_contacts),
            ),
        ],
    )


def _gap_bucket(text: str) -> tuple[str, str] | None:
    normalized = text.lower()
    if "pricing" in normalized or "price" in normalized:
        return "pricing", "Pricing clarity"
    if (
        "implementation" in normalized
        or "setup" in normalized
        or "integration" in normalized
    ):
        return "implementation", "Implementation details"
    if "security" in normalized or "compliance" in normalized:
        return "security", "Security proof"
    if "?" in text or "not sure" in normalized or "don't know" in normalized:
        return "unanswered", "Unanswered buyer question"
    return None


def _build_knowledge_gaps(
    *,
    conversations: list[ChatbotConversation],
    calls: list[tuple[CallRequest, CallSession | None, Contact]],
    session: Session,
) -> list[KnowledgeGapPublic]:
    buckets: dict[str, dict[str, object]] = {}

    def add_evidence(source: str, text: str) -> None:
        bucket = _gap_bucket(text)
        if bucket is None:
            return
        key, title = bucket
        row = buckets.setdefault(
            key,
            {"title": title, "source": source, "evidence": []},
        )
        evidence = row["evidence"]
        if isinstance(evidence, list) and text not in evidence:
            evidence.append(_shorten(text, "Open question.", limit=160))

    for conversation in conversations:
        message = _latest_message(session, conversation)
        if message and message.content:
            add_evidence("chatbot", message.content)
        if conversation.escalation_reason:
            add_evidence("chatbot", conversation.escalation_reason)

    for _, call_session, _ in calls:
        if call_session is None:
            continue
        for question in _extract_questions(call_session.unanswered_questions):
            add_evidence("voice", question)
        if call_session.transcript:
            add_evidence("voice", call_session.transcript)

    gaps: list[KnowledgeGapPublic] = []
    for key, row in buckets.items():
        evidence = row.get("evidence")
        evidence_list = evidence if isinstance(evidence, list) else []
        title = str(row["title"])
        gaps.append(
            KnowledgeGapPublic(
                id=f"gap-{key}",
                title=title,
                source=str(row["source"]),
                evidence_count=len(evidence_list),
                evidence=evidence_list[:3],
                recommended_fix=f"Add {title.lower()} content to the shared knowledge base and active offer packs.",
                priority="high" if key in {"pricing", "security"} else "medium",
            )
        )
    return sorted(gaps, key=lambda gap: (gap.priority != "high", gap.title))[:6]


def _build_offer_recommendations(
    *,
    gaps: list[KnowledgeGapPublic],
    offer_packs: list[OfferPack],
) -> list[OfferRecommendationPublic]:
    if not gaps:
        return []
    first_gap = gaps[0]
    if offer_packs:
        offer = offer_packs[0]
        return [
            OfferRecommendationPublic(
                id=f"offer-{offer.id}",
                title=f"Use {offer.name}",
                reason=f"{first_gap.title} questions are active.",
                recommended_offer=offer.name,
                priority=first_gap.priority,
            )
        ]
    return [
        OfferRecommendationPublic(
            id=f"offer-gap-{first_gap.id}",
            title=f"Create {first_gap.title.lower()} offer pack",
            reason=f"{first_gap.title} is appearing in live buyer conversations.",
            recommended_offer=f"{first_gap.title} response pack",
            priority=first_gap.priority,
        )
    ]


def _build_experiment_recommendations(
    *,
    gaps: list[KnowledgeGapPublic],
    next_best_actions: list[NextBestActionPublic],
) -> list[ExperimentRecommendationPublic]:
    experiments: list[ExperimentRecommendationPublic] = []
    for gap in gaps[:2]:
        experiments.append(
            ExperimentRecommendationPublic(
                id=f"experiment-{gap.id.replace('gap-', '')}",
                title=f"{gap.title} holdout test",
                hypothesis=(
                    f"Adding {gap.title.lower()} content will reduce human "
                    "escalations from high-intent leads."
                ),
                primary_metric="Escalation rate"
                if gap.source == "chatbot"
                else "Follow-up completion rate",
                variants=["Current answer", f"{gap.title} enriched answer"],
                holdout_percent=10,
                eligible_count=max(gap.evidence_count, len(next_best_actions)),
                status="ready"
                if max(gap.evidence_count, len(next_best_actions)) >= 2
                else "draft",
            )
        )

    if not experiments and next_best_actions:
        experiments.append(
            ExperimentRecommendationPublic(
                id="experiment-next-action-channel",
                title="Next action channel holdout test",
                hypothesis=(
                    "Testing the recommended channel against the current "
                    "default will improve completed follow-ups."
                ),
                primary_metric="Completed follow-up rate",
                variants=["Current channel", "AI recommended channel"],
                holdout_percent=10,
                eligible_count=len(next_best_actions),
                status="ready" if len(next_best_actions) >= 2 else "draft",
            )
        )
    return experiments[:4]


def _build_audit_replay(
    audit_events: list[AuditEvent],
) -> list[AuditReplayItemPublic]:
    replay: list[AuditReplayItemPublic] = []
    for event in audit_events[:12]:
        payload = event.payload or {}
        raw_summary = payload.get("summary") or payload.get("description")
        summary = (
            str(raw_summary)
            if raw_summary
            else f"{event.event_name} on {event.resource_type or 'workspace'}."
        )
        replay.append(
            AuditReplayItemPublic(
                id=f"audit-{event.id}",
                event_name=event.event_name,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                actor_role=event.actor_role,
                summary=_shorten(summary, "Audit event recorded."),
                created_at=event.created_at,
                payload=payload,
            )
        )
    return replay


def _provider_channel(provider: str, event: ProviderEventLog | None = None) -> str:
    if event is not None:
        raw_channel = (event.normalized_event or {}).get("channel")
        if isinstance(raw_channel, str) and raw_channel.strip():
            return raw_channel.strip()
    if provider in {
        NotificationProvider.twilio.value,
        NotificationProvider.vapi.value,
    }:
        return "voice"
    if provider in {
        NotificationProvider.facebook_messenger.value,
        NotificationProvider.whatsapp_cloud.value,
        NotificationProvider.telegram_bot.value,
        NotificationProvider.linkedin_redirect.value,
    }:
        return "chatbot"
    return "email"


def _build_provider_health(
    *,
    provider_events: list[ProviderEventLog],
    send_requests: list[tuple[SendRequest, ContactSequenceState, Contact]],
    calls: list[tuple[CallRequest, CallSession | None, Contact]],
) -> list[ProviderHealthPublic]:
    success_events = {
        "accepted",
        "answered",
        "delivered",
        "opened",
        "processed",
        "sent",
    }
    failure_events = {
        "bounce",
        "bounced",
        "complained",
        "deferred",
        "dropped",
        "failed",
        "reject",
        "spam_report",
        "undelivered",
    }
    buckets: dict[
        tuple[str, str],
        dict[str, int | datetime | None],
    ] = {}

    def bucket(provider: str, channel: str) -> dict[str, int | datetime | None]:
        return buckets.setdefault(
            (provider, channel),
            {"success": 0, "failure": 0, "last_event_at": None},
        )

    def touch(
        provider: str,
        channel: str,
        *,
        success: bool = False,
        failure: bool = False,
        occurred_at: datetime | None = None,
    ) -> None:
        row = bucket(provider, channel)
        if success:
            row["success"] = int(row["success"] or 0) + 1
        if failure:
            row["failure"] = int(row["failure"] or 0) + 1
        current = _aware(
            row["last_event_at"] if isinstance(row["last_event_at"], datetime) else None
        )
        candidate = _aware(occurred_at)
        if candidate is not None and (current is None or candidate > current):
            row["last_event_at"] = candidate

    for event in provider_events:
        provider = _provider_value(event.provider)
        channel = _provider_channel(provider, event)
        event_type = event.event_type.lower()
        touch(
            provider,
            channel,
            success=event_type in success_events,
            failure=event_type in failure_events,
            occurred_at=event.received_at,
        )

    email_provider = next(
        (
            _provider_value(event.provider)
            for event in provider_events
            if _provider_channel(_provider_value(event.provider), event) == "email"
        ),
        "email",
    )
    for send_request, _, _ in send_requests:
        touch(
            email_provider,
            "email",
            success=send_request.status == SendRequestStatus.sent,
            failure=send_request.status == SendRequestStatus.failed,
            occurred_at=send_request.sent_at or send_request.created_at,
        )

    for _, call_session, _ in calls:
        if call_session is None:
            continue
        touch(
            NotificationProvider.twilio.value,
            "voice",
            success=call_session.outcome == CallOutcome.answered,
            failure=call_session.outcome in {CallOutcome.failed, CallOutcome.no_answer},
            occurred_at=call_session.created_at,
        )

    health: list[ProviderHealthPublic] = []
    for (provider, channel), row in buckets.items():
        success_count = int(row["success"] or 0)
        failure_count = int(row["failure"] or 0)
        status = (
            "needs_attention"
            if failure_count
            else "healthy"
            if success_count
            else "idle"
        )
        recommended_action = (
            f"Review failed {provider} delivery events and retry blocked contacts."
            if failure_count
            else f"Keep {provider} {channel} monitoring enabled."
            if success_count
            else f"Connect or test the {provider} {channel} provider."
        )
        health.append(
            ProviderHealthPublic(
                id=f"provider-{provider}-{channel}",
                provider=provider,
                channel=channel,
                status=status,
                success_count=success_count,
                failure_count=failure_count,
                last_event_at=row["last_event_at"]
                if isinstance(row["last_event_at"], datetime)
                else None,
                recommended_action=recommended_action,
            )
        )

    return sorted(
        health,
        key=lambda item: (
            item.status != "needs_attention",
            -item.failure_count,
            item.provider,
        ),
    )[:8]


def _pipeline_recommendation(reasons: list[str]) -> str:
    if {
        "Open chatbot escalation",
        "Answered voice call is waiting for scheduling",
        "Failed email send",
    }.issubset(set(reasons)):
        return (
            "Resolve the escalation, repair delivery, and schedule the "
            "requested meeting."
        )
    if "Failed email send" in reasons:
        return "Repair delivery and retry the blocked outreach step."
    if "Open chatbot escalation" in reasons:
        return "Resolve the chatbot escalation before the buyer goes cold."
    if "Answered voice call is waiting for scheduling" in reasons:
        return "Schedule the requested meeting and update the contact state."
    return "Review the stalled contact and choose the next human follow-up."


def _build_pipeline_risks(
    *,
    conversations: list[ChatbotConversation],
    calls: list[tuple[CallRequest, CallSession | None, Contact]],
    send_requests: list[tuple[SendRequest, ContactSequenceState, Contact]],
    sequence_states: list[tuple[ContactSequenceState, Contact]],
    progressions: list[tuple[ContactProgression, Contact]],
    contact_map: dict[uuid.UUID, Contact],
) -> list[PipelineRiskPublic]:
    rows: dict[uuid.UUID, dict[str, object]] = {}

    def add_risk(contact: Contact | None, points: int, reason: str) -> None:
        if contact is None:
            return
        row = rows.setdefault(
            contact.id,
            {"contact": contact, "score": 0, "reasons": []},
        )
        reasons = row["reasons"]
        if isinstance(reasons, list) and reason not in reasons:
            reasons.append(reason)
        row["score"] = int(row["score"]) + points

    for conversation in conversations:
        if conversation.escalated or conversation.status in {
            ChatbotConversationStatus.escalated,
            ChatbotConversationStatus.agent_active,
            ChatbotConversationStatus.bot_paused,
        }:
            contact = (
                contact_map.get(conversation.contact_id)
                if conversation.contact_id
                else None
            )
            add_risk(contact, 35, "Open chatbot escalation")

    for _, call_session, contact in calls:
        if call_session is None:
            continue
        if call_session.scheduling_interest:
            add_risk(
                contact,
                25,
                "Answered voice call is waiting for scheduling",
            )
        if call_session.outcome in {CallOutcome.failed, CallOutcome.no_answer}:
            add_risk(contact, 20, "Voice follow-up did not connect")

    for send_request, _, contact in send_requests:
        if send_request.status == SendRequestStatus.failed:
            add_risk(contact, 25, "Failed email send")

    now = datetime.now(timezone.utc)
    for state, contact in sequence_states:
        next_send_at = _aware(state.next_send_at)
        if state.status == SequenceStatus.active and (
            next_send_at is not None and next_send_at < now
        ):
            add_risk(contact, 15, "Stalled active sequence")

    stale_states = {
        ContactProgressionState.engaged,
        ContactProgressionState.nurturing,
        ContactProgressionState.replied,
    }
    for progression, contact in progressions:
        last_action_at = _aware(progression.last_action_at)
        if progression.current_state in stale_states and (
            last_action_at is not None and (now - last_action_at).days >= 3
        ):
            add_risk(contact, 15, "Engaged contact has no recent action")

    risks: list[PipelineRiskPublic] = []
    for contact_id, row in rows.items():
        contact = row["contact"]
        if not isinstance(contact, Contact):
            continue
        reasons = row["reasons"]
        reason_list = reasons if isinstance(reasons, list) else []
        score = min(100, int(row["score"]))
        risk_level = "high" if score >= 60 else "medium" if score >= 30 else "low"
        risks.append(
            PipelineRiskPublic(
                id=f"risk-{contact_id}",
                contact_id=contact_id,
                contact_name=_contact_name(contact),
                company=contact.company,
                risk_level=risk_level,
                risk_score=score,
                reasons=[str(reason) for reason in reason_list],
                recommended_action=_pipeline_recommendation(
                    [str(reason) for reason in reason_list]
                ),
            )
        )

    return sorted(
        risks,
        key=lambda item: (-item.risk_score, item.contact_name),
    )[:8]


def build_engagement_overview(
    session: Session,
    *,
    workspace_id: str,
) -> EngagementOverviewPublic:
    """Build a deterministic intelligence snapshot for one workspace."""
    (
        contact_map,
        conversations,
        calls,
        snapshots,
        sequence_states,
        offer_packs,
        audit_events,
        provider_events,
        send_requests,
        progressions,
    ) = _load_workspace_data(session, workspace_id)
    gaps = _build_knowledge_gaps(
        conversations=conversations,
        calls=calls,
        session=session,
    )
    next_best_actions = _build_next_best_actions(
        contact_map=contact_map,
        conversations=conversations,
        calls=calls,
        snapshots=snapshots,
        sequence_states=sequence_states,
        session=session,
    )
    unified_inbox = _build_unified_inbox(
        contact_map=contact_map,
        conversations=conversations,
        calls=calls,
        snapshots=snapshots,
        session=session,
    )
    return EngagementOverviewPublic(
        generated_at=datetime.now(timezone.utc),
        next_best_actions=next_best_actions,
        unified_inbox=unified_inbox,
        journey=_build_journey(
            conversations=conversations,
            calls=calls,
            snapshots=snapshots,
            sequence_states=sequence_states,
        ),
        knowledge_gaps=gaps,
        offer_recommendations=_build_offer_recommendations(
            gaps=gaps,
            offer_packs=offer_packs,
        ),
        experiment_recommendations=_build_experiment_recommendations(
            gaps=gaps,
            next_best_actions=next_best_actions,
        ),
        audit_replay=_build_audit_replay(audit_events),
        provider_health=_build_provider_health(
            provider_events=provider_events,
            send_requests=send_requests,
            calls=calls,
        ),
        pipeline_risks=_build_pipeline_risks(
            conversations=conversations,
            calls=calls,
            send_requests=send_requests,
            sequence_states=sequence_states,
            progressions=progressions,
            contact_map=contact_map,
        ),
    )
