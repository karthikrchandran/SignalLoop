from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.lead_preparation.models import LeadScoreBand, LeadScoringPolicy
from app.domain.lead_preparation.scoring import (
    build_default_scoring_policy,
    score_contact,
)
from app.domain.lead_preparation.service import (
    PublishedPolicyImmutableError,
    update_scoring_policy,
)
from app.domain.prospecting.service import score_prospecting_contact
from app.domain_models import Contact


def _contact(**overrides: object) -> Contact:
    values: dict[str, object] = {
        "workspace_id": "ara-sales",
        "email": "ada@example.com",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "company": "Analytical",
        "phone": "+15551234567",
        "source_channel": "web",
        "tags_json": ["chatbot-lead", "web"],
        "intent_json": ["pricing-request", "demo-request"],
    }
    values.update(overrides)
    return Contact(**values)


def test_default_policy_reproduces_current_explainable_score() -> None:
    now = datetime(2026, 8, 16, 12, tzinfo=timezone.utc)
    contact = _contact(last_seen_at=now - timedelta(days=2))
    policy = build_default_scoring_policy(
        tenant_id=uuid.uuid4(), workspace_id=contact.workspace_id, version=1
    )

    result = score_contact(contact=contact, policy=policy, now=now)
    legacy = score_prospecting_contact(contact)

    assert result.score == 100
    assert result.score == legacy.lead_score
    assert result.band == LeadScoreBand.HOT
    assert result.policy_version == 1
    assert sum(item.points for item in result.contributions) == result.score
    assert {item.feature for item in result.contributions} == {
        "buyer_intent",
        "company_known",
        "email_available",
        "messaging_handoff",
        "recent_activity",
        "voice_ready",
    }


def test_stale_activity_is_explained_but_does_not_score_as_recent() -> None:
    now = datetime(2026, 8, 16, 12, tzinfo=timezone.utc)
    contact = _contact(last_seen_at=now - timedelta(days=91))
    policy = build_default_scoring_policy(
        tenant_id=uuid.uuid4(), workspace_id=contact.workspace_id, version=2
    )

    result = score_contact(contact=contact, policy=policy, now=now)

    assert result.score == 90
    assert "ACTIVITY_STALE" in result.negative_factors
    assert "Recent activity" not in result.reasons


def test_suppression_makes_contact_not_eligible_without_channel_drafts() -> None:
    contact = _contact(suppressed=True, consent_email=True, consent_voice=True)
    policy = build_default_scoring_policy(
        tenant_id=uuid.uuid4(), workspace_id=contact.workspace_id, version=1
    )

    result = score_contact(contact=contact, policy=policy)

    assert result.score == 0
    assert result.band == LeadScoreBand.NOT_ELIGIBLE
    assert result.exclusions == ["CONTACT_SUPPRESSED"]


def test_missing_consent_keeps_score_but_marks_channels_ineligible() -> None:
    contact = _contact(consent_email=False, consent_voice=False)
    policy = build_default_scoring_policy(
        tenant_id=uuid.uuid4(), workspace_id=contact.workspace_id, version=1
    )

    result = score_contact(contact=contact, policy=policy)

    assert result.score == 90
    assert result.channel_eligibility == {"email": False, "voice": False}
    assert "EMAIL_CONSENT_MISSING" in result.negative_factors
    assert "VOICE_CONSENT_MISSING" in result.negative_factors


def test_published_policy_cannot_be_mutated_in_place() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine,
        tables=[LeadScoringPolicy.__table__],
    )
    with Session(engine) as session:
        policy = build_default_scoring_policy(
            tenant_id=uuid.uuid4(), workspace_id="ara-sales", version=1
        )
        session.add(policy)
        session.commit()

        with pytest.raises(PublishedPolicyImmutableError):
            update_scoring_policy(
                session,
                policy_id=policy.id,
                feature_weights={**policy.feature_weights, "buyer_intent": 30},
            )

        session.refresh(policy)
        assert policy.feature_weights["buyer_intent"] == 25
