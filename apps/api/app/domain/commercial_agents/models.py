"""Durable commercial registry for independently configured SignalLoop agents."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentType(str, Enum):
    LEAD_PREPARATION = "LEAD_PREPARATION"
    EMAIL_OUTREACH = "EMAIL_OUTREACH"
    VOICE_CONVERSATION = "VOICE_CONVERSATION"
    CHAT_LEAD_CAPTURE = "CHAT_LEAD_CAPTURE"
    CAMPAIGN_MANAGER = "CAMPAIGN_MANAGER"
    PROPOSAL_DRAFTING = "PROPOSAL_DRAFTING"
    CALENDAR_SCHEDULER = "CALENDAR_SCHEDULER"
    REVENUE_INTERVENTION = "REVENUE_INTERVENTION"
    SALES_DAY_ASSISTANT = "SALES_DAY_ASSISTANT"


class AgentDeploymentStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEGRADED = "DEGRADED"
    RETIRING = "RETIRING"
    RETIRED = "RETIRED"


class AgentUsageState(str, Enum):
    RESERVED = "RESERVED"
    FINALIZED = "FINALIZED"
    RELEASED = "RELEASED"
    UNKNOWN = "UNKNOWN"


class AgentCatalogDefinition(SQLModel, table=True):  # type: ignore[call-arg]
    """Immutable published definition for one commercial agent type/version."""

    __tablename__ = "agent_catalog_definition"
    __table_args__ = (
        UniqueConstraint(
            "agent_type", "catalog_version", name="uq_agent_catalog_type_version"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    agent_type: AgentType = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    catalog_version: int = Field(nullable=False)
    display_name: str = Field(max_length=255)
    sellable_outcome: str = Field(max_length=1000)
    lifecycle_status: str = Field(default="PUBLISHED", max_length=32, index=True)
    default_capacity_metric: str = Field(max_length=64)
    default_capacity_amount: int = Field(gt=0)
    capacity_period: str = Field(default="DAY", max_length=16)
    default_concurrency: int | None = Field(default=None, gt=0)
    required_capabilities: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    external_side_effects: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False)
    )
    configuration_schema_version: str = Field(max_length=128)
    approved_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    deprecated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AgentPlanEntitlement(SQLModel, table=True):  # type: ignore[call-arg]
    """Tenant contract governing purchasable agent slots."""

    __tablename__ = "agent_plan_entitlement"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "installation_id",
            "contract_version",
            name="uq_agent_plan_tenant_installation_contract",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    installation_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_product_installation.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    plan_code: str = Field(max_length=128)
    contract_version: str = Field(max_length=128)
    purchased_slots: int = Field(gt=0)
    allowed_agent_types: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    type_ceilings: dict[str, int] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    overage_policy: str = Field(default="BLOCK", max_length=32)
    billing_timezone: str = Field(default="UTC", max_length=64)
    billing_day_start_hour: int = Field(default=0, ge=0, le=23)
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    effective_from: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    effective_to: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    contract_reference: str | None = Field(default=None, max_length=255)
    approved_by: uuid.UUID | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AgentDeployment(SQLModel, table=True):  # type: ignore[call-arg]
    """One independently configured, slot-consuming commercial agent."""

    __tablename__ = "agent_deployment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_agent_deployment_tenant_name"),
        Index("ix_agent_deployment_tenant_status", "tenant_id", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    installation_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_product_installation.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    catalog_definition_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("agent_catalog_definition.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    agent_type: AgentType = Field(
        sa_column=Column(String(64), nullable=False, index=True)
    )
    name: str = Field(max_length=255)
    purpose: str | None = Field(default=None, max_length=1000)
    owner_user_id: uuid.UUID | None = Field(default=None)
    status: AgentDeploymentStatus = Field(
        default=AgentDeploymentStatus.DRAFT,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    configuration: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    configuration_digest: str = Field(max_length=64)
    policy_profile: str | None = Field(default=None, max_length=128)
    locale: str = Field(default="en-US", max_length=32)
    timezone: str = Field(default="UTC", max_length=64)
    environment: str = Field(default="production", max_length=32)
    lifecycle_version: int = Field(default=1, ge=1)
    activated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    suspended_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    retired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    last_health_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AgentDependency(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "agent_dependency"
    __table_args__ = (
        UniqueConstraint(
            "source_deployment_id",
            "target_deployment_id",
            "dependency_type",
            name="uq_agent_dependency_edge",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    source_deployment_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("agent_deployment.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    target_deployment_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("agent_deployment.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    dependency_type: str = Field(max_length=64)
    minimum_catalog_version: int | None = Field(default=None)
    health_requirement: str = Field(default="ACTIVE", max_length=32)
    status: str = Field(default="ACTIVE", max_length=32, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AgentCapacityOverride(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "agent_capacity_override"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    deployment_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("agent_deployment.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    capacity_metric: str = Field(max_length=64)
    capacity_amount: int = Field(gt=0)
    concurrency_limit: int | None = Field(default=None, gt=0)
    effective_from: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    effective_to: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    reason: str = Field(max_length=500)
    approved_by: uuid.UUID = Field()
    contract_reference: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AgentUsageLedger(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "agent_usage_ledger"
    __table_args__ = (
        UniqueConstraint(
            "deployment_id",
            "capacity_metric",
            "idempotency_key",
            name="uq_agent_usage_deployment_metric_key",
        ),
        Index(
            "ix_agent_usage_deployment_day_state",
            "deployment_id",
            "billing_day",
            "state",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    workspace_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    deployment_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("agent_deployment.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    billing_day: date = Field(sa_column=Column(Date, nullable=False, index=True))
    capacity_metric: str = Field(max_length=64)
    idempotency_key: str = Field(max_length=255)
    state: AgentUsageState = Field(
        default=AgentUsageState.RESERVED,
        sa_column=Column(String(32), nullable=False, index=True),
    )
    reserved_units: int = Field(default=1, gt=0)
    finalized_units: int = Field(default=0, ge=0)
    provider_units: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    provider_receipt_id: str | None = Field(default=None, max_length=255)
    failure_reason: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AgentLifecycleEvent(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "agent_lifecycle_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("suite_tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    deployment_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("agent_deployment.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    event_type: str = Field(max_length=128, index=True)
    lifecycle_version: int = Field(ge=1)
    actor_id: uuid.UUID | None = Field(default=None)
    actor_role: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    recorded_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
