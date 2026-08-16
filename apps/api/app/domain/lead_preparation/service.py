"""Transactional administration for immutable lead-scoring policies."""

from __future__ import annotations

import uuid
from typing import Any

from sqlmodel import Session

from app.domain.lead_preparation.models import (
    LeadScoringPolicy,
    LeadScoringPolicyStatus,
)


class LeadPreparationError(ValueError):
    """Base error for deterministic lead-preparation rules."""


class PublishedPolicyImmutableError(LeadPreparationError):
    """A published policy must be superseded by a new version."""


def update_scoring_policy(
    session: Session,
    *,
    policy_id: uuid.UUID,
    feature_weights: dict[str, int] | None = None,
    band_thresholds: dict[str, int] | None = None,
    freshness_windows: dict[str, int] | None = None,
    exclusion_rules: list[str] | None = None,
) -> LeadScoringPolicy:
    """Update a draft; published history is immutable by service contract."""

    policy = session.get(LeadScoringPolicy, policy_id)
    if policy is None:
        raise LeadPreparationError("lead scoring policy was not found")
    if policy.status is not LeadScoringPolicyStatus.DRAFT:
        raise PublishedPolicyImmutableError(
            "published lead scoring policies must be superseded"
        )
    changes: dict[str, Any] = {
        "feature_weights": feature_weights,
        "band_thresholds": band_thresholds,
        "freshness_windows": freshness_windows,
        "exclusion_rules": exclusion_rules,
    }
    for field, value in changes.items():
        if value is not None:
            setattr(policy, field, value)
    session.add(policy)
    session.flush()
    return policy
