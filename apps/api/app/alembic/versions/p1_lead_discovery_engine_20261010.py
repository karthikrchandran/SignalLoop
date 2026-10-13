"""Add lead discovery and AI enrichment tables.

Revision ID: p1_lead_discovery_engine_20261010
Revises: p1_calendar_lifecycle_hardening_20260816
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p1_lead_discovery_engine_20261010"
down_revision = "p1_calendar_lifecycle_hardening_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovered_leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("seniority", sa.String(length=64), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("company_domain", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("revenue_range", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("tech_stack_json", sa.JSON(), nullable=False),
        sa.Column("intent_signals_json", sa.JSON(), nullable=False),
        sa.Column("source_provider", sa.String(length=64), nullable=False, server_default="SANDBOX"),
        sa.Column("match_confidence", sa.String(length=64), nullable=False, server_default="NEW_ENTITY"),
        sa.Column("matched_account_id", sa.String(length=128), nullable=True),
        sa.Column("fit_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fit_band", sa.String(length=32), nullable=False, server_default="UNQUALIFIED"),
        sa.Column("score_rationale", sa.String(length=2000), nullable=True),
        sa.Column("conversation_starters_json", sa.JSON(), nullable=False),
        sa.Column("is_promoted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("promoted_contact_id", sa.Uuid(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_disc_lead_workspace_email",
        "discovered_leads",
        ["workspace_id", "email"],
    )
    op.create_index(
        "ix_disc_lead_workspace_domain",
        "discovered_leads",
        ["workspace_id", "company_domain"],
    )
    op.create_index(
        "ix_disc_lead_fit_score",
        "discovered_leads",
        ["workspace_id", "fit_score"],
    )

    op.create_table(
        "discovery_search_query_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("criteria_json", sa.JSON(), nullable=False),
        sa.Column("results_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_used", sa.String(length=64), nullable=False, server_default="SANDBOX"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_discovery_search_query_logs_workspace_id",
        "discovery_search_query_logs",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_search_query_logs_workspace_id", table_name="discovery_search_query_logs")
    op.drop_table("discovery_search_query_logs")
    op.drop_index("ix_disc_lead_fit_score", table_name="discovered_leads")
    op.drop_index("ix_disc_lead_workspace_domain", table_name="discovered_leads")
    op.drop_index("ix_disc_lead_workspace_email", table_name="discovered_leads")
    op.drop_table("discovered_leads")
