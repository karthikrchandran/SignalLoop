"""Explainable deterministic lead scoring under an immutable policy version."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

from app.domain.lead_preparation.models import (
    LeadScoreBand,
    LeadScoringPolicy,
    LeadScoringPolicyStatus,
)
from app.domain_models import Contact

DEFAULT_FEATURE_WEIGHTS = {
    "messaging_handoff": 35,
    "buyer_intent": 25,
    "voice_ready": 15,
    "company_known": 10,
    "recent_activity": 10,
    "email_available": 5,
}
DEFAULT_BAND_THRESHOLDS = {"HOT": 70, "WARM": 40}
DEFAULT_FRESHNESS_WINDOWS = {"recent_activity_days": 30}
DEFAULT_EXCLUSIONS = ["do_not_contact", "suppressed"]


class ScoreContribution(SQLModel):
    feature: str
    points: int
    reason: str
    evidence_value: str | bool | int | None = None


class LeadScoreResult(SQLModel):
    score: int = Field(ge=0, le=100)
    band: LeadScoreBand
    policy_id: uuid.UUID
    policy_version: int
    contributions: list[ScoreContribution]
    reasons: list[str]
    negative_factors: list[str]
    exclusions: list[str]
    channel_eligibility: dict[str, bool]
    feature_vector: dict[str, bool | int | str | None]


def _policy_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_default_scoring_policy(
    *, tenant_id: uuid.UUID, workspace_id: str, version: int
) -> LeadScoringPolicy:
    payload: dict[str, object] = {
        "feature_weights": DEFAULT_FEATURE_WEIGHTS,
        "band_thresholds": DEFAULT_BAND_THRESHOLDS,
        "freshness_windows": DEFAULT_FRESHNESS_WINDOWS,
        "exclusion_rules": DEFAULT_EXCLUSIONS,
        "version": version,
    }
    return LeadScoringPolicy(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        version=version,
        status=LeadScoringPolicyStatus.PUBLISHED,
        feature_weights=dict(DEFAULT_FEATURE_WEIGHTS),
        band_thresholds=dict(DEFAULT_BAND_THRESHOLDS),
        freshness_windows=dict(DEFAULT_FRESHNESS_WINDOWS),
        exclusion_rules=list(DEFAULT_EXCLUSIONS),
        policy_digest=_policy_digest(payload),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _has_buyer_intent(values: list[str]) -> bool:
    intent_text = " ".join(value.strip().lower() for value in values)
    return any(
        token in intent_text
        for token in ("pricing", "demo", "purchase", "trial", "quote", "sales")
    )


def score_contact(
    *,
    contact: Contact,
    policy: LeadScoringPolicy,
    now: datetime | None = None,
) -> LeadScoreResult:
    """Score one contact with deterministic features and explicit exclusions."""

    at = _as_utc(now or datetime.now(timezone.utc))
    exclusions: list[str] = []
    if contact.do_not_contact:
        exclusions.append("DO_NOT_CONTACT")
    if contact.suppressed:
        exclusions.append("CONTACT_SUPPRESSED")
    email_available = not contact.email.endswith("@chatbot.local.invalid")
    channel_eligibility = {
        "email": bool(contact.consent_email and email_available and not exclusions),
        "voice": bool(contact.consent_voice and contact.phone and not exclusions),
    }
    negative_factors: list[str] = []
    if not contact.consent_email:
        negative_factors.append("EMAIL_CONSENT_MISSING")
    if not contact.consent_voice:
        negative_factors.append("VOICE_CONSENT_MISSING")
    if exclusions:
        return LeadScoreResult(
            score=0,
            band=LeadScoreBand.NOT_ELIGIBLE,
            policy_id=policy.id,
            policy_version=policy.version,
            contributions=[],
            reasons=[],
            negative_factors=negative_factors,
            exclusions=exclusions,
            channel_eligibility=channel_eligibility,
            feature_vector={"eligible": False},
        )

    normalized_tags = {value.strip().lower() for value in contact.tags_json}
    messaging_handoff = "chatbot-lead" in normalized_tags or bool(contact.source_channel)
    buyer_intent = _has_buyer_intent(contact.intent_json)
    recent_activity = False
    if contact.last_seen_at:
        age_days = max(0, (at - _as_utc(contact.last_seen_at)).days)
        recent_activity = age_days <= policy.freshness_windows.get(
            "recent_activity_days", 30
        )
        if not recent_activity:
            negative_factors.append("ACTIVITY_STALE")
    features: dict[str, tuple[bool, str, str | bool | int | None]] = {
        "messaging_handoff": (
            messaging_handoff,
            "Captured from Messaging Hub",
            contact.source_channel,
        ),
        "buyer_intent": (buyer_intent, "Buyer intent detected", ",".join(contact.intent_json)),
        "voice_ready": (bool(contact.phone), "Voice ready", bool(contact.phone)),
        "company_known": (bool(contact.company), "Company known", contact.company),
        "recent_activity": (recent_activity, "Recent activity", contact.last_seen_at.isoformat() if contact.last_seen_at else None),
        "email_available": (email_available, "Email available", email_available),
    }
    contributions = [
        ScoreContribution(
            feature=feature,
            points=policy.feature_weights.get(feature, 0),
            reason=reason,
            evidence_value=evidence,
        )
        for feature, (enabled, reason, evidence) in features.items()
        if enabled and policy.feature_weights.get(feature, 0) > 0
    ]
    score = min(100, sum(item.points for item in contributions))
    hot = policy.band_thresholds.get("HOT", 70)
    warm = policy.band_thresholds.get("WARM", 40)
    band = LeadScoreBand.HOT if score >= hot else LeadScoreBand.WARM if score >= warm else LeadScoreBand.NURTURE
    return LeadScoreResult(
        score=score,
        band=band,
        policy_id=policy.id,
        policy_version=policy.version,
        contributions=contributions,
        reasons=[item.reason for item in contributions],
        negative_factors=negative_factors,
        exclusions=[],
        channel_eligibility=channel_eligibility,
        feature_vector={feature: enabled for feature, (enabled, _, _) in features.items()},
    )
