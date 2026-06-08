from __future__ import annotations

from app.domain.prospecting.schemas import ProspectingSource
from app.domain.prospecting.service import build_prospecting_brief
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
