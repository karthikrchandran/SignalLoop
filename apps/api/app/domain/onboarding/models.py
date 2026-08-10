from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class OnboardingStage(str, Enum):
    TENANT_DRAFTED = "TENANT_DRAFTED"
    PRODUCTS_ASSIGNED = "PRODUCTS_ASSIGNED"
    ENTRY_CONFIGURED = "ENTRY_CONFIGURED"
    OWNER_INVITED = "OWNER_INVITED"
    ROLES_ASSIGNED = "ROLES_ASSIGNED"
    POLICIES_PUBLISHED = "POLICIES_PUBLISHED"
    NATIVE_INTEGRATION_VERIFIED = "NATIVE_INTEGRATION_VERIFIED"
    READY_FOR_ACCEPTANCE = "READY_FOR_ACCEPTANCE"
    ACTIVE = "ACTIVE"


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def can_transition(current: StageStatus | str, next_status: StageStatus | str) -> bool:
    current = StageStatus(current)
    next_status = StageStatus(next_status)
    return {
        StageStatus.PENDING: {StageStatus.RUNNING},
        StageStatus.RUNNING: {StageStatus.SUCCEEDED, StageStatus.FAILED},
        StageStatus.FAILED: {StageStatus.RUNNING},
        StageStatus.SUCCEEDED: set(),
    }[current].__contains__(next_status)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StageResult:
    stage: OnboardingStage
    status: StageStatus = StageStatus.PENDING
    attempts: int = 0
    result_code: str | None = None
    evidence_refs: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class OnboardingRun:
    tenant_key: str
    desired_version: str = "phase1"
    idempotency_key: str | None = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: StageStatus = StageStatus.PENDING
    stages: dict[OnboardingStage, StageResult] = field(default_factory=dict)
    attempts: int = 0
    actor: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            self.idempotency_key = f"onboarding:{self.tenant_key}:{self.desired_version}"
        self.stages = self.stages or {stage: StageResult(stage) for stage in OnboardingStage}
