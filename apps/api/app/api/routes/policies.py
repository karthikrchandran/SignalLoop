from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select

from app.api.deps import SessionDep
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.domain.audit.mongo_audit import append_audit_event
from app.domain_models import (
    CampaignPolicyBinding,
    GovernancePoliciesPublic,
    GovernancePolicy,
    GovernancePolicyCreate,
    GovernancePolicyPublic,
    PolicyDecision,
    PolicyEvaluationRequest,
    PolicyStatus,
    PolicyType,
)
from app.domain.policies.policy_engine import evaluate_policies
from app.infrastructure.authz.enforcer import require_permission, require_role

router = APIRouter(prefix="/policies", tags=["policies"])


def _require_payload_fields(payload: dict, required_fields: list[str]) -> None:
    missing = [field for field in required_fields if field not in payload]
    if missing:
        missing_text = ", ".join(missing)
        raise HTTPException(status_code=400, detail=f"Policy payload is missing required fields: {missing_text}")


def _validate_policy_payload(*, policy_type: PolicyType | str, payload: dict) -> None:
    if policy_type == "quiet_hours":
        _require_payload_fields(payload, ["start", "end", "timezone"])
        try:
            time.fromisoformat(str(payload["start"]))
            time.fromisoformat(str(payload["end"]))
        except ValueError as error:
            raise HTTPException(status_code=400, detail="quiet_hours policy requires HH:MM values for start and end") from error

    if policy_type == "daily_caps":
        _require_payload_fields(payload, ["systemDailyCap", "campaignDailyCap"])
        try:
            if int(payload["systemDailyCap"]) < 0 or int(payload["campaignDailyCap"]) < 0:
                raise HTTPException(status_code=400, detail="daily_caps values must be non-negative")
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="daily_caps values must be valid integers") from error


@router.get("/", response_model=GovernancePoliciesPublic, dependencies=[Depends(require_role("operator")), Depends(require_permission("/policies", "read"))])
def read_policies(session: SessionDep, workspace_id: WorkspaceIdDep) -> GovernancePoliciesPublic:
    policies = session.exec(select(GovernancePolicy).where(GovernancePolicy.workspace_id == workspace_id)).all()
    return GovernancePoliciesPublic(
        data=[
            GovernancePolicyPublic(
                id=policy.id,
                scope=policy.scope,
                policy_type=policy.policy_type,
                status=policy.status,
                payload_json=policy.payload_json,
            )
            for policy in policies
        ],
        count=len(policies),
    )


@router.post("/", response_model=GovernancePolicyPublic, dependencies=[Depends(require_role("admin")), Depends(require_permission("/policies", "write"))])
async def create_policy(
    *,
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: GovernancePolicyCreate,
) -> GovernancePolicyPublic:
    _validate_policy_payload(policy_type=body.policy_type, payload=body.payload_json)
    policy = GovernancePolicy(workspace_id=workspace_id, **body.model_dump())
    session.add(policy)
    session.commit()
    session.refresh(policy)
    await append_audit_event(
        event_name="policy.created",
        workspace_id=workspace_id,
        payload={
            "policy_id": str(policy.id),
            "policy_type": str(body.policy_type),
            "scope": body.scope,
            "correlation_id": getattr(request.state, "request_id", ""),
        },
    )
    return GovernancePolicyPublic(
        id=policy.id,
        scope=policy.scope,
        policy_type=policy.policy_type,
        status=policy.status,
        payload_json=policy.payload_json,
    )


@router.post("/evaluate", response_model=PolicyDecision, dependencies=[Depends(require_role("operator")), Depends(require_permission("/policies", "evaluate"))])
def evaluate_policy_decision(*, session: SessionDep, workspace_id: WorkspaceIdDep, body: PolicyEvaluationRequest) -> PolicyDecision:
    query = select(GovernancePolicy).where(
        GovernancePolicy.workspace_id == workspace_id,
        GovernancePolicy.status == PolicyStatus.active,
    )
    policies = list(session.exec(query).all())

    if body.campaign_id is not None:
        bound_policy_ids = {
            binding.policy_id
            for binding in session.exec(
                select(CampaignPolicyBinding)
                .join(GovernancePolicy, GovernancePolicy.id == CampaignPolicyBinding.policy_id)
                .where(
                    CampaignPolicyBinding.campaign_id == body.campaign_id,
                    GovernancePolicy.workspace_id == workspace_id,
                )
            ).all()
        }
        policies = [
            policy
            for policy in policies
            if policy.campaign_id in {None, body.campaign_id} or policy.id in bound_policy_ids
        ]

    return evaluate_policies(
        policies=policies,
        contact=body.contact,
        campaign_daily_count=body.campaign_daily_count,
        system_daily_count=body.system_daily_count,
        requested_at=body.requested_at,
    )
