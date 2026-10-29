"""Internal AI scoring engine and opportunity brief synthesis for discovered leads."""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.lead_discovery.models import LeadFitBand
from app.domain.lead_discovery.schemas import (
    DiscoveredLeadDTO,
    LeadScoreContribution,
    LeadScoringResponse,
)

_HIGH_INTENT_KEYWORDS = {
    "intent",
    "automation",
    "evaluating",
    "hiring",
    "scaling",
    "funding",
    "crm",
    "outbound",
    "sales",
    "pipeline",
    "growth",
}


def score_discovered_lead(
    lead: DiscoveredLeadDTO,
    target_industries: Sequence[str] | None = None,
    ideal_employee_range: tuple[int, int] | None = None,
) -> LeadScoringResponse:
    """Calculate multi-dimensional score and synthesize AI brief for a discovered lead."""
    contributions: list[LeadScoreContribution] = []

    # 1. Firmographic Fit (0 - 35 points)
    firmo_pts = 0
    firmo_reasons: list[str] = []

    # Industry match (up to 15 pts)
    target_inds = [ind.lower() for ind in (target_industries or [])]
    lead_ind = (lead.industry or "").lower()
    if target_inds and any(target in lead_ind or lead_ind in target for target in target_inds):
        firmo_pts += 15
        firmo_reasons.append(f"Industry ({lead.industry}) matches target ICP")
    elif lead.industry:
        firmo_pts += 8
        firmo_reasons.append(f"Industry identified as {lead.industry}")
    else:
        firmo_reasons.append("Industry unknown")

    # Employee range (up to 10 pts)
    emp = lead.employee_count or 0
    if ideal_employee_range and ideal_employee_range[0] <= emp <= ideal_employee_range[1]:
        firmo_pts += 10
        firmo_reasons.append(f"Headcount ({emp}) in sweet spot {ideal_employee_range[0]}-{ideal_employee_range[1]}")
    elif emp > 0:
        firmo_pts += 5
        firmo_reasons.append(f"Headcount ({emp}) verified")

    # Revenue bracket (up to 10 pts)
    if lead.revenue_range:
        firmo_pts += 10
        firmo_reasons.append(f"Revenue range {lead.revenue_range} reported")

    contributions.append(
        LeadScoreContribution(
            pillar="firmographic_fit",
            points=min(firmo_pts, 35),
            max_points=35,
            reason="; ".join(firmo_reasons) or "Basic firmographics",
        )
    )

    # 2. Intent & Trigger Signals (0 - 30 points)
    intent_pts = 0
    intent_reasons: list[str] = []
    signals_text = " ".join(lead.intent_signals).lower()

    matched_keywords = [kw for kw in _HIGH_INTENT_KEYWORDS if kw in signals_text]
    if matched_keywords:
        intent_pts += min(len(matched_keywords) * 5, 15)
        intent_reasons.append(f"Triggers matched: {', '.join(matched_keywords[:3])}")

    if lead.intent_signals:
        breadth_pts = min(len(lead.intent_signals) * 7, 15)
        intent_pts += breadth_pts
        intent_reasons.append(f"{len(lead.intent_signals)} active market signals observed")

    contributions.append(
        LeadScoreContribution(
            pillar="intent_signals",
            points=min(intent_pts, 30),
            max_points=30,
            reason="; ".join(intent_reasons) or "No active intent signals detected",
        )
    )

    # 3. Role & Seniority Authority (0 - 20 points)
    role_pts = 5
    title = (lead.title or "").lower()
    seniority = (lead.seniority or "").lower()

    if any(term in title or term in seniority for term in ["vp", "vice president", "c-level", "chief", "founder", "owner", "partner"]):
        role_pts = 20
        role_reason = f"Executive decision maker ({lead.title})"
    elif any(term in title or term in seniority for term in ["director", "head of"]):
        role_pts = 15
        role_reason = f"Department leadership ({lead.title})"
    elif any(term in title or term in seniority for term in ["manager", "lead"]):
        role_pts = 10
        role_reason = f"Functional manager ({lead.title})"
    else:
        role_reason = f"Individual contributor or unverified role ({lead.title or 'Unknown'})"

    contributions.append(
        LeadScoreContribution(
            pillar="role_authority",
            points=role_pts,
            max_points=20,
            reason=role_reason,
        )
    )

    # 4. Data Completeness & Reachability (0 - 15 points)
    comp_pts = 0
    comp_reasons: list[str] = []
    if lead.email and "@" in lead.email:
        comp_pts += 8
        comp_reasons.append("Verified email")
    if lead.phone:
        comp_pts += 4
        comp_reasons.append("Phone contact")
    if lead.tech_stack:
        comp_pts += 3
        comp_reasons.append(f"{len(lead.tech_stack)} tech stack items")

    contributions.append(
        LeadScoreContribution(
            pillar="data_completeness",
            points=min(comp_pts, 15),
            max_points=15,
            reason="; ".join(comp_reasons) or "Basic contact information",
        )
    )

    total_score = sum(c.points for c in contributions)
    total_score = max(0, min(total_score, 100))

    if total_score >= 80:
        band = LeadFitBand.HOT_OPPORTUNITY
    elif total_score >= 60:
        band = LeadFitBand.HIGH_FIT
    elif total_score >= 40:
        band = LeadFitBand.NURTURE
    else:
        band = LeadFitBand.UNQUALIFIED

    # AI Rationale and conversation angle synthesis
    company = lead.company_name
    primary_tech = lead.tech_stack[0] if lead.tech_stack else "their modern stack"
    signal_summary = lead.intent_signals[0] if lead.intent_signals else f"scaling initiatives at {company}"

    rationale = (
        f"High-priority prospect at {company}. {lead.first_name} holds {lead.title or 'leadership'} authority "
        f"in an organization showing strong signals ({signal_summary}). "
        f"Firmographic profile and stack ({primary_tech}) indicate high probability for automated workflow adoption."
    )

    conversation_starters = [
        f"Email Angle: Noticed {company}'s focus on {signal_summary.lower()} — curious how your team handles outbound efficiency?",
        f"Voice Angle: Hi {lead.first_name}, calling regarding {company}'s current stack around {primary_tech} and sales pipeline automation.",
    ]

    channels = ["email"]
    if lead.phone:
        channels.append("phone")

    return LeadScoringResponse(
        fit_score=total_score,
        fit_band=band,
        contributions=contributions,
        rationale=rationale,
        conversation_starters=conversation_starters,
        suggested_channels=channels,
    )
