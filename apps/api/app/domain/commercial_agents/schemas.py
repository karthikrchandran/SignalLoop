"""Strict request and response schemas for commercial agent administration."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.commercial_agents.models import AgentDeploymentStatus, AgentType

_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "password",
    "private_key",
    "secret",
    "token",
}


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _SECRET_KEYS or _contains_secret_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


class AgentDeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installation_id: uuid.UUID
    workspace_id: str = Field(min_length=1, max_length=64)
    catalog_definition_id: uuid.UUID
    agent_type: AgentType
    name: str = Field(min_length=2, max_length=255)
    purpose: str | None = Field(default=None, max_length=1000)
    owner_user_id: uuid.UUID | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    policy_profile: str | None = Field(default=None, max_length=128)
    locale: str = Field(default="en-US", min_length=2, max_length=32)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    environment: str = Field(
        default="production", pattern=r"^(local|staging|production)$"
    )

    @field_validator("configuration")
    @classmethod
    def reject_inline_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_secret_key(value):
            raise ValueError(
                "configuration must contain credential references, not secrets"
            )
        return value


class AgentLifecycleReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class AgentEntitlementChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    installation_id: uuid.UUID
    plan_code: str = Field(min_length=2, max_length=128)
    contract_version: str = Field(min_length=1, max_length=128)
    purchased_slots: int = Field(gt=0, le=10_000)
    allowed_agent_types: list[AgentType] = Field(default_factory=list)
    type_ceilings: dict[AgentType, int] = Field(default_factory=dict)
    billing_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    billing_day_start_hour: int = Field(default=0, ge=0, le=23)
    contract_reference: str | None = Field(default=None, max_length=255)

    @field_validator("type_ceilings")
    @classmethod
    def validate_type_ceilings(
        cls, value: dict[AgentType, int]
    ) -> dict[AgentType, int]:
        if any(limit < 1 for limit in value.values()):
            raise ValueError("type ceilings must be positive")
        return value

    @field_validator("billing_timezone")
    @classmethod
    def validate_billing_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("billing timezone must be an IANA timezone") from exc
        return value


class AgentDeploymentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    installation_id: uuid.UUID
    workspace_id: str
    catalog_definition_id: uuid.UUID
    agent_type: AgentType
    name: str
    purpose: str | None
    status: AgentDeploymentStatus
    policy_profile: str | None
    locale: str
    timezone: str
    environment: str
    lifecycle_version: int
    activated_at: datetime | None
    suspended_at: datetime | None
    retired_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentCatalogPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_type: AgentType
    catalog_version: int
    display_name: str
    sellable_outcome: str
    lifecycle_status: str
    default_capacity_metric: str
    default_capacity_amount: int
    capacity_period: str
    default_concurrency: int | None
    configuration_schema_version: str


class AgentEntitlementPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    installation_id: uuid.UUID
    plan_code: str
    contract_version: str
    purchased_slots: int
    allowed_agent_types: list[str]
    type_ceilings: dict[str, int]
    billing_timezone: str
    billing_day_start_hour: int
    status: str
