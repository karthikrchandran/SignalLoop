from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.prospecting.schemas import (
    ProspectingBrief,
    ProspectingEnrollmentPublic,
    ProspectingReadyContactPublic,
    ProspectingResearchPublic,
    ProspectingSource,
)
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SequenceStatus,
)
from app.domain.shared_records import service as shared_record_service
from app.domain_models import (
    Campaign,
    Contact,
    ContactEvent,
    ContactProgression,
    ContactProgressionState,
    ContactPublic,
    ContactStateHistory,
    ProspectingSnapshot,
)
from app.infrastructure.rag.crawler import crawl_website


class ProspectingContactNotFoundError(Exception):
    """Raised when the requested contact is not in the active workspace."""


class ProspectingCampaignNotFoundError(Exception):
    """Raised when the requested campaign is not in the active workspace."""


class ProspectingSequenceNotFoundError(Exception):
    """Raised when the requested sequence is not in the active workspace or campaign."""


def _contact_name(contact: Contact) -> str:
    name = " ".join(part for part in [contact.first_name, contact.last_name] if part)
    return name or contact.email


def _first_name(contact: Contact) -> str:
    return contact.first_name or _contact_name(contact).split("@", 1)[0]


def _company_name(contact: Contact) -> str:
    if contact.company:
        return contact.company
    domain = contact.email.split("@", 1)[1] if "@" in contact.email else "the account"
    return domain


def _contact_from_public(contact: ContactPublic) -> Contact:
    return Contact(
        id=contact.id,
        workspace_id=contact.workspace_id,
        shared_account_id=contact.account_id,
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        phone=contact.phone,
        timezone=contact.timezone,
        source_channel=contact.source_channel,
        tags_json=list(contact.tags_json or []),
        intent_json=list(contact.intent_json or []),
        last_seen_at=contact.last_seen_at,
        created_at=contact.created_at,
    )


def _compact(values: list[str]) -> list[str]:
    seen: set[str] = set()
    compacted: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            compacted.append(normalized)
    return compacted


def _normalized_values(values: list[str] | None) -> set[str]:
    return {
        value.strip().lower() for value in (values or []) if value and value.strip()
    }


def _has_buyer_intent(intents: set[str]) -> bool:
    intent_text = " ".join(intents)
    return any(
        token in intent_text
        for token in ["pricing", "demo", "purchase", "trial", "quote", "sales"]
    )


def score_prospecting_contact(contact: Contact) -> ProspectingReadyContactPublic:
    """Score one contact for near-term prospecting follow-up."""
    tags = list(contact.tags_json or [])
    intents = list(contact.intent_json or [])
    normalized_tags = _normalized_values(tags)
    normalized_intents = _normalized_values(intents)
    is_handoff = "chatbot-lead" in normalized_tags or bool(contact.source_channel)

    score = 0
    reasons: list[str] = []
    if is_handoff:
        score += 35
        reasons.append("Captured from Messaging Hub")
    if _has_buyer_intent(normalized_intents):
        score += 25
        reasons.append("Buyer intent detected")
    if contact.phone:
        score += 15
        reasons.append("Voice ready")
    if contact.company:
        score += 10
        reasons.append("Company known")
    if contact.last_seen_at:
        score += 10
        reasons.append("Recent activity")
    if not contact.email.endswith("@chatbot.local.invalid"):
        score += 5
        reasons.append("Email available")

    score = min(score, 100)
    priority = "high" if score >= 70 else "medium" if score >= 40 else "low"

    return ProspectingReadyContactPublic(
        id=contact.id,
        workspace_id=contact.workspace_id,
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        company=contact.company,
        phone=contact.phone,
        timezone=contact.timezone,
        source_channel=contact.source_channel,
        tags=tags,
        intents=intents,
        lead_score=score,
        priority=priority,
        priority_reasons=reasons,
        handoff_source=contact.source_channel if is_handoff else None,
        created_at=contact.created_at,
    )


def list_ready_contacts(
    _session: Session,
    *,
    workspace_id: str,
    search: str | None = None,
    only_handoffs: bool = False,
    limit: int = 20,
) -> list[ProspectingReadyContactPublic]:
    """Return workspace contacts ranked for prospecting."""
    shared_contacts = shared_record_service.list_shared_contacts(
        workspace_id=workspace_id,
        search=search,
        limit=200,
    )
    contacts = [
        contact if isinstance(contact, Contact) else _contact_from_public(contact)
        for contact in shared_contacts
    ]
    scored = [score_prospecting_contact(contact) for contact in contacts]
    if only_handoffs:
        scored = [contact for contact in scored if contact.handoff_source]
    if search and search.strip():
        query = search.strip().lower()

        def matches(contact: ProspectingReadyContactPublic) -> bool:
            haystack = " ".join(
                [
                    contact.email,
                    contact.first_name or "",
                    contact.last_name or "",
                    contact.company or "",
                    contact.source_channel or "",
                    *contact.tags,
                    *contact.intents,
                ]
            ).lower()
            return query in haystack

        scored = [contact for contact in scored if matches(contact)]
    scored.sort(
        key=lambda contact: (contact.lead_score, contact.created_at), reverse=True
    )
    return scored[:limit]


def _source_text(sources: list[ProspectingSource]) -> str:
    return " ".join(source.summary for source in sources).lower()


def _crm_contact_source(contact: Contact) -> ProspectingSource:
    fragments = [
        f"{_contact_name(contact)} at {_company_name(contact)}",
        f"email {contact.email}",
    ]
    if contact.tags_json:
        fragments.append(f"tags: {', '.join(contact.tags_json)}")
    if contact.intent_json:
        fragments.append(f"intent: {', '.join(contact.intent_json)}")
    if contact.last_seen_at:
        fragments.append(f"last seen at {contact.last_seen_at.isoformat()}")
    return ProspectingSource(label="CRM contact", summary="; ".join(fragments))


def _timeline_sources(
    session: Session, *, workspace_id: str, contact_id: uuid.UUID
) -> list[ProspectingSource]:
    shared_contact_id = contact_id
    contact_events = session.exec(
        select(ContactEvent)
        .where(
            ContactEvent.workspace_id == workspace_id,
            ContactEvent.shared_contact_id == shared_contact_id,
        )
        .order_by(ContactEvent.created_at.desc())
        .limit(5)
    ).all()
    state_history = session.exec(
        select(ContactStateHistory)
        .where(
            ContactStateHistory.workspace_id == workspace_id,
            ContactStateHistory.shared_contact_id == shared_contact_id,
        )
        .order_by(ContactStateHistory.triggered_at.desc())
        .limit(5)
    ).all()

    summaries: list[str] = []
    for event in contact_events:
        parts = [event.event_type]
        if event.channel:
            parts.append(f"on {event.channel}")
        if event.outcome:
            parts.append(f"outcome {event.outcome}")
        if event.reason_code:
            parts.append(f"reason {event.reason_code}")
        summaries.append(" ".join(parts))
    for state in state_history:
        summaries.append(
            f"state moved from {state.from_state.value} to {state.to_state.value}"
        )

    if not summaries:
        return []
    return [ProspectingSource(label="CRM timeline", summary="; ".join(summaries))]


async def _website_sources(company_url: str | None) -> list[ProspectingSource]:
    if not company_url or not company_url.strip():
        return []

    normalized_url = company_url.strip()
    try:
        pages = await crawl_website(normalized_url, depth=1, max_pages=3)
    except Exception:  # noqa: BLE001
        return [
            ProspectingSource(
                label="Website unavailable",
                summary=f"{normalized_url} could not be crawled, so this brief uses CRM data only.",
            )
        ]

    if not pages:
        return [
            ProspectingSource(
                label="Website",
                summary=f"{normalized_url} returned no extractable website text.",
            )
        ]

    sources: list[ProspectingSource] = []
    for page in pages:
        text = " ".join(page.text.split())
        excerpt = text[:420] + ("..." if len(text) > 420 else "")
        sources.append(
            ProspectingSource(
                label=f"Website: {page.title[:100]}",
                summary=f"{page.url}: {excerpt}",
            )
        )
    return sources


def build_prospecting_brief(
    *, contact: Contact, sources: list[ProspectingSource]
) -> ProspectingBrief:
    """Build a deterministic prospecting brief from CRM and source snippets."""
    name = _contact_name(contact)
    first_name = _first_name(contact)
    company = _company_name(contact)
    text = _source_text(sources)
    source_labels = ", ".join(source.label for source in sources[:3]) or "CRM context"

    account_summary = (
        f"{name} is a prospect at {company}. SignalLoop has CRM context from {source_labels}. "
        "Use this brief as sales research, not as verified live-news intelligence."
    )

    pain_points = [
        "Turn scattered CRM activity into a focused next outreach step.",
        "Improve outreach conversion with messaging that reflects the account context.",
    ]
    if contact.intent_json:
        pain_points.append(
            f"Respond to declared intent around {', '.join(contact.intent_json)}."
        )
    if "pricing" in text:
        pain_points.append(
            "Clarify pricing fit and value quickly because pricing intent is present."
        )
    if "follow-up" in text or "outbound" in text or "conversion" in text:
        pain_points.append(
            "Tighten outbound follow-up so interest does not stall after first engagement."
        )
    if contact.phone:
        pain_points.append(
            "Coordinate email and voice touchpoints without losing context between channels."
        )

    objections = [
        "May already have a CRM, enrichment, or sales engagement workflow.",
        "May need proof that personalization can be generated without adding manual research time.",
    ]
    if "pricing" in text or any(
        "pricing" in value.lower() for value in contact.intent_json
    ):
        objections.append("May ask for pricing clarity before agreeing to a call.")

    personalization = [
        f"Reference {company} directly and keep the ask specific to one next step.",
        f"Use {first_name}'s recent CRM context instead of a generic industry opener.",
    ]
    if contact.tags_json:
        personalization.append(
            f"Mention the signal behind {', '.join(contact.tags_json[:2])}."
        )
    if sources:
        personalization.append(
            f"Anchor the message in {sources[0].label.lower()}: {sources[0].summary[:140]}."
        )

    suggested_next_action = "Send a short value-led email, then use the voice opener as a same-day follow-up if the account is high fit."

    primary_signal = personalization[-1].rstrip(".")
    email_draft = (
        f"Subject: Idea for {company}'s outreach follow-up\n\n"
        f"Hi {first_name},\n\n"
        f"I noticed {primary_signal}. SignalLoop can help your team turn CRM and conversation history into "
        "more relevant email and voice follow-up without adding manual research work.\n\n"
        "Would it be worth a short conversation to compare where your current outreach process is losing context?\n\n"
        "Best,\n"
        "SignalLoop"
    )
    voice_opener = (
        f"Hi {first_name}, this is SignalLoop calling about {company}. "
        "I am following up with one specific idea for turning your existing CRM activity into more personalized outreach."
    )

    return ProspectingBrief(
        account_summary=account_summary,
        pain_points=_compact(pain_points),
        objections=_compact(objections),
        personalization_bullets=_compact(personalization),
        suggested_next_action=suggested_next_action,
        email_draft=email_draft,
        voice_opener=voice_opener,
    )


async def create_prospecting_snapshot(
    *,
    session: Session,
    workspace_id: str,
    contact_id: uuid.UUID,
    company_url: str | None,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
) -> ProspectingSnapshot:
    """Create and persist a prospecting research snapshot."""
    shared_contact = shared_record_service.get_shared_contact(
        workspace_id=workspace_id,
        contact_id=contact_id,
    )
    contact = _contact_from_public(shared_contact) if shared_contact else None
    if contact is None:
        raise ProspectingContactNotFoundError

    sources = [_crm_contact_source(contact)]
    sources.extend(
        _timeline_sources(session, workspace_id=workspace_id, contact_id=contact.id)
    )
    sources.extend(await _website_sources(company_url))
    brief = build_prospecting_brief(contact=contact, sources=sources)

    snapshot = ProspectingSnapshot(
        workspace_id=workspace_id,
        shared_contact_id=contact.id,
        created_by=actor_id,
        company_url=company_url.strip() if company_url else None,
        sources_json=[source.model_dump() for source in sources],
        research_json=brief.model_dump(),
        email_draft=brief.email_draft,
        voice_opener=brief.voice_opener,
    )
    session.add(snapshot)
    session.flush()
    append_audit_event_to_session(
        session,
        event_name="prospect.researched",
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type="prospecting_snapshot",
        resource_id=str(snapshot.id),
        payload={
            "contact_id": str(contact.id),
            "company_url": snapshot.company_url,
            "source_count": len(sources),
        },
    )
    session.commit()
    session.refresh(snapshot)
    return snapshot


def _unique_ids(values: list[uuid.UUID]) -> list[uuid.UUID]:
    return list(dict.fromkeys(values))


def _load_selected_contacts(
    *,
    _session: Session,
    workspace_id: str,
    contact_ids: list[uuid.UUID],
) -> list[Contact]:
    unique_contact_ids = _unique_ids(contact_ids)
    contacts = []
    for contact_id in unique_contact_ids:
        contact = shared_record_service.get_shared_contact(
            workspace_id=workspace_id,
            contact_id=contact_id,
        )
        if contact is None:
            raise ProspectingContactNotFoundError
        contacts.append(_contact_from_public(contact))
    if len(contacts) != len(unique_contact_ids):
        raise ProspectingContactNotFoundError
    return contacts


async def create_bulk_prospecting_snapshots(
    *,
    session: Session,
    workspace_id: str,
    contact_ids: list[uuid.UUID],
    company_url: str | None,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
) -> list[ProspectingSnapshot]:
    """Create prospecting snapshots for selected workspace contacts."""
    contacts = _load_selected_contacts(
        _session=session, workspace_id=workspace_id, contact_ids=contact_ids
    )
    snapshots: list[ProspectingSnapshot] = []
    for contact in contacts:
        snapshots.append(
            await create_prospecting_snapshot(
                session=session,
                workspace_id=workspace_id,
                contact_id=contact.id,
                company_url=company_url,
                actor_id=actor_id,
                actor_role=actor_role,
            )
        )
    return snapshots


def enroll_selected_prospects(
    *,
    session: Session,
    workspace_id: str,
    contact_ids: list[uuid.UUID],
    campaign_id: uuid.UUID,
    sequence_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    actor_role: str | None,
) -> ProspectingEnrollmentPublic:
    """Add selected prospects to a campaign and optionally to one sequence."""
    contacts = _load_selected_contacts(
        _session=session, workspace_id=workspace_id, contact_ids=contact_ids
    )
    campaign = session.exec(
        select(Campaign).where(
            Campaign.workspace_id == workspace_id, Campaign.id == campaign_id
        )
    ).first()
    if campaign is None:
        raise ProspectingCampaignNotFoundError

    sequence: EmailSequence | None = None
    if sequence_id is not None:
        sequence = session.exec(
            select(EmailSequence)
            .join(Campaign, EmailSequence.campaign_id == Campaign.id)
            .where(
                EmailSequence.id == sequence_id,
                EmailSequence.campaign_id == campaign_id,
                Campaign.workspace_id == workspace_id,
            )
        ).first()
        if sequence is None:
            raise ProspectingSequenceNotFoundError

    campaign_added_count = 0
    campaign_existing_count = 0
    sequence_enrolled_count = 0
    sequence_existing_count = 0

    for contact in contacts:
        progression = session.exec(
            select(ContactProgression).where(
                ContactProgression.shared_contact_id == contact.id,
                ContactProgression.campaign_id == campaign_id,
            )
        ).first()
        if progression:
            campaign_existing_count += 1
        else:
            session.add(
                ContactProgression(
                    shared_contact_id=contact.id,
                    campaign_id=campaign_id,
                    current_state=ContactProgressionState.inbox,
                )
            )
            campaign_added_count += 1

        if sequence is None:
            continue
        sequence_state = session.exec(
            select(ContactSequenceState).where(
                ContactSequenceState.shared_contact_id == contact.id,
                ContactSequenceState.sequence_id == sequence.id,
            )
        ).first()
        if sequence_state:
            sequence_existing_count += 1
        else:
            session.add(
                ContactSequenceState(
                    workspace_id=workspace_id,
                    shared_contact_id=contact.id,
                    sequence_id=sequence.id,
                    status=SequenceStatus.active,
                    signal_type="prospecting",
                )
            )
            sequence_enrolled_count += 1

    append_audit_event_to_session(
        session,
        event_name="prospecting.contacts_enrolled",
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type="campaign",
        resource_id=str(campaign_id),
        payload={
            "campaign_id": str(campaign_id),
            "sequence_id": str(sequence_id) if sequence_id else None,
            "selected_count": len(contacts),
            "campaign_added_count": campaign_added_count,
            "campaign_existing_count": campaign_existing_count,
            "sequence_enrolled_count": sequence_enrolled_count,
            "sequence_existing_count": sequence_existing_count,
        },
    )
    session.commit()

    message = f"Added {campaign_added_count} prospects to {campaign.name}."
    if sequence is not None:
        message = (
            f"Added {campaign_added_count} prospects to {campaign.name} and enrolled "
            f"{sequence_enrolled_count} in {sequence.name}."
        )
    return ProspectingEnrollmentPublic(
        selected_count=len(contacts),
        campaign_added_count=campaign_added_count,
        campaign_existing_count=campaign_existing_count,
        sequence_enrolled_count=sequence_enrolled_count,
        sequence_existing_count=sequence_existing_count,
        message=message,
    )


def list_prospecting_snapshots(
    *,
    session: Session,
    workspace_id: str,
    contact_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[ProspectingSnapshot]:
    """Return recent prospecting snapshots for one workspace."""
    statement = select(ProspectingSnapshot).where(
        ProspectingSnapshot.workspace_id == workspace_id
    )
    if contact_id is not None:
        statement = statement.where(
            ProspectingSnapshot.shared_contact_id == contact_id
        )
    return list(
        session.exec(
            statement.order_by(ProspectingSnapshot.created_at.desc()).limit(limit)
        ).all()
    )


def snapshot_to_public(snapshot: ProspectingSnapshot) -> ProspectingResearchPublic:
    """Convert a persisted snapshot into the public response model."""
    brief = ProspectingBrief(**snapshot.research_json)
    sources = [ProspectingSource(**source) for source in snapshot.sources_json]
    return ProspectingResearchPublic(
        id=snapshot.id,
        contact_id=snapshot.shared_contact_id,
        company_url=snapshot.company_url,
        sources=sources,
        created_at=snapshot.created_at,
        **brief.model_dump(),
    )
