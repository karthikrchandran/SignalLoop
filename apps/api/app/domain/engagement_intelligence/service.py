"""Read-only engagement intelligence assembled from existing workspace data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session, SQLModel, select

from app.domain.chatbot.models import (
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotMessage,
)
from app.domain.sequences.models import ContactSequenceState, SequenceStatus
from app.domain.voice.models import CallRequest, CallSession
from app.domain_models import Contact, OfferPack, ProspectingSnapshot


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


class EngagementOverviewPublic(SQLModel):
    generated_at: datetime
    next_best_actions: list[NextBestActionPublic]
    unified_inbox: list[UnifiedInboxItemPublic]
    journey: JourneyCanvasPublic
    knowledge_gaps: list[KnowledgeGapPublic]
    offer_recommendations: list[OfferRecommendationPublic]


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
    return contact_map, conversations, calls, snapshots, sequence_states, offer_packs


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
                    conversation.escalation_reason or message.content
                    if message
                    else None,
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


def build_engagement_overview(
    session: Session,
    *,
    workspace_id: str,
) -> EngagementOverviewPublic:
    """Build a deterministic intelligence snapshot for one workspace."""
    contact_map, conversations, calls, snapshots, sequence_states, offer_packs = (
        _load_workspace_data(session, workspace_id)
    )
    gaps = _build_knowledge_gaps(
        conversations=conversations,
        calls=calls,
        session=session,
    )
    return EngagementOverviewPublic(
        generated_at=datetime.now(timezone.utc),
        next_best_actions=_build_next_best_actions(
            contact_map=contact_map,
            conversations=conversations,
            calls=calls,
            snapshots=snapshots,
            sequence_states=sequence_states,
            session=session,
        ),
        unified_inbox=_build_unified_inbox(
            contact_map=contact_map,
            conversations=conversations,
            calls=calls,
            snapshots=snapshots,
            session=session,
        ),
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
    )
