"""Add the durable commercial agent registry.

Revision ID: p1_commercial_agent_registry_20260816
Revises: p1_tenant_workspace_binding_20260812
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_commercial_agent_registry_20260816"
down_revision = "p1_tenant_workspace_binding_20260812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_catalog_definition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("sellable_outcome", sa.String(1000), nullable=False),
        sa.Column("lifecycle_status", sa.String(32), nullable=False),
        sa.Column("default_capacity_metric", sa.String(64), nullable=False),
        sa.Column("default_capacity_amount", sa.Integer(), nullable=False),
        sa.Column("capacity_period", sa.String(16), nullable=False),
        sa.Column("default_concurrency", sa.Integer(), nullable=True),
        sa.Column("required_capabilities", sa.JSON(), nullable=False),
        sa.Column("external_side_effects", sa.Boolean(), nullable=False),
        sa.Column("configuration_schema_version", sa.String(128), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_type", "catalog_version", name="uq_agent_catalog_type_version"
        ),
    )
    op.create_index(
        "ix_agent_catalog_definition_agent_type",
        "agent_catalog_definition",
        ["agent_type"],
    )
    op.create_index(
        "ix_agent_catalog_definition_lifecycle_status",
        "agent_catalog_definition",
        ["lifecycle_status"],
    )

    op.create_table(
        "agent_plan_entitlement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(128), nullable=False),
        sa.Column("contract_version", sa.String(128), nullable=False),
        sa.Column("purchased_slots", sa.Integer(), nullable=False),
        sa.Column("allowed_agent_types", sa.JSON(), nullable=False),
        sa.Column("type_ceilings", sa.JSON(), nullable=False),
        sa.Column("overage_policy", sa.String(32), nullable=False),
        sa.Column("billing_timezone", sa.String(64), nullable=False),
        sa.Column("billing_day_start_hour", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contract_reference", sa.String(255), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["installation_id"], ["suite_product_installation.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "installation_id",
            "contract_version",
            name="uq_agent_plan_tenant_installation_contract",
        ),
    )
    op.create_index(
        "ix_agent_plan_entitlement_tenant_id", "agent_plan_entitlement", ["tenant_id"]
    )
    op.create_index(
        "ix_agent_plan_entitlement_installation_id",
        "agent_plan_entitlement",
        ["installation_id"],
    )
    op.create_index(
        "ix_agent_plan_entitlement_status", "agent_plan_entitlement", ["status"]
    )

    op.create_table(
        "agent_deployment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("catalog_definition_id", sa.Uuid(), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(1000), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("configuration_digest", sa.String(64), nullable=False),
        sa.Column("policy_profile", sa.String(128), nullable=True),
        sa.Column("locale", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("lifecycle_version", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_definition_id"],
            ["agent_catalog_definition.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["installation_id"], ["suite_product_installation.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_agent_deployment_tenant_name"
        ),
    )
    for column in (
        "tenant_id",
        "installation_id",
        "workspace_id",
        "agent_type",
        "status",
    ):
        op.create_index(f"ix_agent_deployment_{column}", "agent_deployment", [column])
    op.create_index(
        "ix_agent_deployment_tenant_status", "agent_deployment", ["tenant_id", "status"]
    )

    op.create_table(
        "agent_dependency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_deployment_id", sa.Uuid(), nullable=False),
        sa.Column("target_deployment_id", sa.Uuid(), nullable=False),
        sa.Column("dependency_type", sa.String(64), nullable=False),
        sa.Column("minimum_catalog_version", sa.Integer(), nullable=True),
        sa.Column("health_requirement", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_deployment_id"], ["agent_deployment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_deployment_id"], ["agent_deployment.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_deployment_id",
            "target_deployment_id",
            "dependency_type",
            name="uq_agent_dependency_edge",
        ),
    )
    for column in (
        "tenant_id",
        "source_deployment_id",
        "target_deployment_id",
        "status",
    ):
        op.create_index(f"ix_agent_dependency_{column}", "agent_dependency", [column])

    op.create_table(
        "agent_capacity_override",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("capacity_metric", sa.String(64), nullable=False),
        sa.Column("capacity_amount", sa.Integer(), nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=False),
        sa.Column("contract_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["deployment_id"], ["agent_deployment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_capacity_override_tenant_id", "agent_capacity_override", ["tenant_id"]
    )
    op.create_index(
        "ix_agent_capacity_override_deployment_id",
        "agent_capacity_override",
        ["deployment_id"],
    )

    op.create_table(
        "agent_usage_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("billing_day", sa.Date(), nullable=False),
        sa.Column("capacity_metric", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("reserved_units", sa.Integer(), nullable=False),
        sa.Column("finalized_units", sa.Integer(), nullable=False),
        sa.Column("provider_units", sa.JSON(), nullable=False),
        sa.Column("provider_receipt_id", sa.String(255), nullable=True),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["deployment_id"], ["agent_deployment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deployment_id",
            "capacity_metric",
            "idempotency_key",
            name="uq_agent_usage_deployment_metric_key",
        ),
    )
    for column in (
        "tenant_id",
        "workspace_id",
        "deployment_id",
        "billing_day",
        "state",
    ):
        op.create_index(
            f"ix_agent_usage_ledger_{column}", "agent_usage_ledger", [column]
        )
    op.create_index(
        "ix_agent_usage_deployment_day_state",
        "agent_usage_ledger",
        ["deployment_id", "billing_day", "state"],
    )

    op.create_table(
        "agent_lifecycle_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("lifecycle_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(64), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["deployment_id"], ["agent_deployment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["suite_tenant.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "deployment_id", "event_type"):
        op.create_index(
            f"ix_agent_lifecycle_event_{column}", "agent_lifecycle_event", [column]
        )


def downgrade() -> None:
    for table, indexes in (
        ("agent_lifecycle_event", ["tenant_id", "deployment_id", "event_type"]),
        (
            "agent_usage_ledger",
            ["tenant_id", "workspace_id", "deployment_id", "billing_day", "state"],
        ),
        ("agent_capacity_override", ["tenant_id", "deployment_id"]),
        (
            "agent_dependency",
            ["tenant_id", "source_deployment_id", "target_deployment_id", "status"],
        ),
        (
            "agent_deployment",
            ["tenant_id", "installation_id", "workspace_id", "agent_type", "status"],
        ),
        ("agent_plan_entitlement", ["tenant_id", "installation_id", "status"]),
        ("agent_catalog_definition", ["agent_type", "lifecycle_status"]),
    ):
        if table == "agent_usage_ledger":
            op.drop_index("ix_agent_usage_deployment_day_state", table_name=table)
        if table == "agent_deployment":
            op.drop_index("ix_agent_deployment_tenant_status", table_name=table)
        for column in indexes:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_table(table)
