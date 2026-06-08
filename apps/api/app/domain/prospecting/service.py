from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.prospecting.schemas import (
    ProspectingBrief,
    ProspectingResearchPublic,
    ProspectingSource,
)
from app.domain_models import (
    Contact,
    ContactEvent,
    ContactStateHistory,
    ProspectingSnapshot,
)
from app.infrastructure.rag.crawler import crawl_website


class ProspectingContactNotFoundError(Exception):
    """Raised when the requested contact is not in the active workspace."""


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


def _timeline_sources(session: Session, *, workspace_id: str, contact_id: uuid.UUID) -> list[ProspectingSource]:
    contact_events = session.exec(
        select(ContactEvent)
        .where(ContactEvent.workspace_id == workspace_id, ContactEvent.contact_id == contact_id)
        .order_by(ContactEvent.created_at.desc())
        .limit(5)
    ).all()
    state_history = session.exec(
        select(ContactStateHistory)
        .where(ContactStateHistory.workspace_id == workspace_id, ContactStateHistory.contact_id == contact_id)
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
        summaries.append(f"state moved from {state.from_state.value} to {state.to_state.value}")

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


def build_prospecting_brief(*, contact: Contact, sources: list[ProspectingSource]) -> ProspectingBrief:
    """Build a deterministic prospecting brief from CRM and source snippets."""
    name = _contact_name(contact)
    first_name = _first_name(contact)
    company = _company_name(contact)
    text = _source_text(sources)
    source_labels = ", ".join(source.label for source in sources[:3]) or "CRM context"

    account_summary = (
        f"{name} is a prospect at {company}. EngageHub has CRM context from {source_labels}. "
        "Use this brief as sales research, not as verified live-news intelligence."
    )

    pain_points = [
        "Turn scattered CRM activity into a focused next outreach step.",
        "Improve outreach conversion with messaging that reflects the account context.",
    ]
    if contact.intent_json:
        pain_points.append(f"Respond to declared intent around {', '.join(contact.intent_json)}.")
    if "pricing" in text:
        pain_points.append("Clarify pricing fit and value quickly because pricing intent is present.")
    if "follow-up" in text or "outbound" in text or "conversion" in text:
        pain_points.append("Tighten outbound follow-up so interest does not stall after first engagement.")
    if contact.phone:
        pain_points.append("Coordinate email and voice touchpoints without losing context between channels.")

    objections = [
        "May already have a CRM, enrichment, or sales engagement workflow.",
        "May need proof that personalization can be generated without adding manual research time.",
    ]
    if "pricing" in text or any("pricing" in value.lower() for value in contact.intent_json):
        objections.append("May ask for pricing clarity before agreeing to a call.")

    personalization = [
        f"Reference {company} directly and keep the ask specific to one next step.",
        f"Use {first_name}'s recent CRM context instead of a generic industry opener.",
    ]
    if contact.tags_json:
        personalization.append(f"Mention the signal behind {', '.join(contact.tags_json[:2])}.")
    if sources:
        personalization.append(f"Anchor the message in {sources[0].label.lower()}: {sources[0].summary[:140]}.")

    suggested_next_action = (
        "Send a short value-led email, then use the voice opener as a same-day follow-up if the account is high fit."
    )

    primary_signal = personalization[-1].rstrip(".")
    email_draft = (
        f"Subject: Idea for {company}'s outreach follow-up\n\n"
        f"Hi {first_name},\n\n"
        f"I noticed {primary_signal}. EngageHub can help your team turn CRM and conversation history into "
        "more relevant email and voice follow-up without adding manual research work.\n\n"
        "Would it be worth a short conversation to compare where your current outreach process is losing context?\n\n"
        "Best,\n"
        "EngageHub"
    )
    voice_opener = (
        f"Hi {first_name}, this is EngageHub calling about {company}. "
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
    contact = session.exec(
        select(Contact).where(Contact.workspace_id == workspace_id, Contact.id == contact_id)
    ).first()
    if contact is None:
        raise ProspectingContactNotFoundError

    sources = [_crm_contact_source(contact)]
    sources.extend(_timeline_sources(session, workspace_id=workspace_id, contact_id=contact.id))
    sources.extend(await _website_sources(company_url))
    brief = build_prospecting_brief(contact=contact, sources=sources)

    snapshot = ProspectingSnapshot(
        workspace_id=workspace_id,
        contact_id=contact.id,
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


def list_prospecting_snapshots(
    *,
    session: Session,
    workspace_id: str,
    contact_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[ProspectingSnapshot]:
    """Return recent prospecting snapshots for one workspace."""
    statement = select(ProspectingSnapshot).where(ProspectingSnapshot.workspace_id == workspace_id)
    if contact_id is not None:
        statement = statement.where(ProspectingSnapshot.contact_id == contact_id)
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
        contact_id=snapshot.contact_id,
        company_url=snapshot.company_url,
        sources=sources,
        created_at=snapshot.created_at,
        **brief.model_dump(),
    )
