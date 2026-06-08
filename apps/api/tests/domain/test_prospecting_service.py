from __future__ import annotations

from app.domain.prospecting.schemas import ProspectingSource
from app.domain.prospecting.service import build_prospecting_brief, score_prospecting_contact
from app.domain_models import Contact


def test_build_prospecting_brief_uses_contact_signals_and_sources() -> None:
    contact = Contact(
        workspace_id="ws-prospecting-unit",
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company="Analytical",
        tags_json=["chatbot-lead", "pricing"],
        intent_json=["pricing-request"],
    )
    sources = [
        ProspectingSource(
            label="Company website",
            summary="Analytical helps revenue teams improve outbound conversion and automate follow-up.",
        ),
        ProspectingSource(
            label="CRM timeline",
            summary="Recent pricing request and chatbot lead capture.",
        ),
    ]

    brief = build_prospecting_brief(contact=contact, sources=sources)

    assert "Ada" in brief.account_summary
    assert "Analytical" in brief.account_summary
    assert len(brief.pain_points) >= 2
    assert any("conversion" in point.lower() or "follow-up" in point.lower() for point in brief.pain_points)
    assert len(brief.objections) >= 1
    assert len(brief.personalization_bullets) >= 2
    assert "Subject:" in brief.email_draft
    assert "Ada" in brief.email_draft
    assert "Ada" in brief.voice_opener


def test_score_prospecting_contact_prioritizes_chatbot_handoff() -> None:
    contact = Contact(
        workspace_id="ws-prospecting-unit",
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company="Analytical",
        phone="+15551234567",
        source_channel="web",
        tags_json=["chatbot-lead", "web"],
        intent_json=["pricing-request", "demo-request"],
    )

    scored = score_prospecting_contact(contact)

    assert scored.lead_score >= 80
    assert scored.priority == "high"
    assert scored.handoff_source == "web"
    assert "Captured from Messaging Hub" in scored.priority_reasons
    assert "Buyer intent detected" in scored.priority_reasons
    assert "Voice ready" in scored.priority_reasons
