"""Live SignalLoop policy enforcement for RevenueOS provider dispatch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlmodel import Session, select

from app.domain.policies.consent_sync_service import is_contact_actionable
from app.domain.policies.policy_engine import evaluate_policies
from app.domain.sequences.suppression import is_email_suppressed
from app.domain_models import (
    ActionQueue,
    Contact,
    GlobalControlState,
    GovernancePolicy,
    PolicyStatus,
)

from .persistence_models import RevenueSignalRecord


@dataclass(frozen=True)
class InterventionEnforcementDecision:
    """Normalized allow, deny, or defer result recorded before provider execution."""

    allowed: bool
    reason: str | None = None
    next_attempt_at: datetime | None = None


class PersistedSignalEnforcementGate:
    """Minimum fail-closed gate retained for isolated domain callers and tests."""

    def evaluate(
        self,
        *,
        action: str,
        payload: dict[str, object],
        signal: RevenueSignalRecord,
    ) -> InterventionEnforcementDecision:
        del action, payload
        if not signal.consent_verified:
            return InterventionEnforcementDecision(False, "CONSENT_NOT_VERIFIED")
        if not signal.policy_allowed:
            return InterventionEnforcementDecision(False, "POLICY_NOT_ALLOWED")
        return InterventionEnforcementDecision(True)


class ConfiguredInterventionEnforcementGate(PersistedSignalEnforcementGate):
    """Re-evaluate current SignalLoop contact and policy state for a workspace."""

    def __init__(
        self,
        *,
        session: Session,
        workspace_id: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.workspace_id = workspace_id
        self.now = now or (lambda: datetime.now(UTC))

    def evaluate(
        self,
        *,
        action: str,
        payload: dict[str, object],
        signal: RevenueSignalRecord,
    ) -> InterventionEnforcementDecision:
        snapshot = super().evaluate(action=action, payload=payload, signal=signal)
        if not snapshot.allowed:
            return snapshot
        if action != "send_email":
            return InterventionEnforcementDecision(False, "UNSUPPORTED_ACTION")

        contact_id = _uuid_value(payload.get("contact_id"))
        recipient = payload.get("to")
        if contact_id is None or not isinstance(recipient, str) or not recipient.strip():
            return InterventionEnforcementDecision(False, "ACTION_CONTEXT_REQUIRED")
        contact = self.session.exec(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.workspace_id == self.workspace_id,
            )
        ).one_or_none()
        if contact is None or contact.email.casefold() != recipient.strip().casefold():
            return InterventionEnforcementDecision(False, "CONTACT_TARGET_MISMATCH")

        actionable, reason = is_contact_actionable(contact.model_dump(), "email")
        if not actionable:
            return InterventionEnforcementDecision(False, reason or "EMAIL_CONSENT_REQUIRED")
        if is_email_suppressed(self.session, self.workspace_id, contact.email):
            return InterventionEnforcementDecision(False, "EMAIL_SUPPRESSED")

        campaign_id = _uuid_value(payload.get("campaign_id"))
        if self._paused(campaign_id):
            return InterventionEnforcementDecision(
                False,
                "CAMPAIGN_PAUSED" if campaign_id else "WORKSPACE_PAUSED",
                self.now() + timedelta(minutes=5),
            )

        policies = list(
            self.session.exec(
                select(GovernancePolicy).where(
                    GovernancePolicy.workspace_id == self.workspace_id,
                    GovernancePolicy.status == PolicyStatus.active,
                    (GovernancePolicy.campaign_id.is_(None))
                    | (GovernancePolicy.campaign_id == campaign_id),
                )
            ).all()
        )
        now = self.now()
        start_of_day = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        system_count = int(
            self.session.exec(
                select(func.count())
                .select_from(ActionQueue)
                .where(
                    ActionQueue.workspace_id == self.workspace_id,
                    ActionQueue.executed_at >= start_of_day,
                )
            ).one()
        )
        campaign_count = 0
        if campaign_id is not None:
            campaign_count = int(
                self.session.exec(
                    select(func.count())
                    .select_from(ActionQueue)
                    .where(
                        ActionQueue.workspace_id == self.workspace_id,
                        ActionQueue.campaign_id == campaign_id,
                        ActionQueue.executed_at >= start_of_day,
                    )
                ).one()
            )
        decision = evaluate_policies(
            policies=policies,
            contact=contact.model_dump(),
            campaign_daily_count=campaign_count,
            system_daily_count=system_count,
            requested_at=now,
        )
        if decision.allowed:
            return InterventionEnforcementDecision(True)
        retry_at = decision.next_eligible_at
        if retry_at is None and decision.reason_code in {
            "SYSTEM_CAP_EXCEEDED",
            "CAMPAIGN_CAP_EXCEEDED",
        }:
            retry_at = start_of_day + timedelta(days=1)
        return InterventionEnforcementDecision(
            False,
            decision.reason_code or "POLICY_NOT_ALLOWED",
            retry_at,
        )

    def _paused(self, campaign_id: UUID | None) -> bool:
        rows = self.session.exec(
            select(GlobalControlState).where(
                GlobalControlState.workspace_id == self.workspace_id,
                GlobalControlState.paused == True,  # noqa: E712
            )
        ).all()
        return any(row.campaign_id is None or row.campaign_id == campaign_id for row in rows)


def _uuid_value(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None
