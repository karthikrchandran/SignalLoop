"""Seed the version-one commercial agent catalog.

Revision ID: p1_commercial_agent_catalog_20260816
Revises: p1_commercial_agent_registry_20260816
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "p1_commercial_agent_catalog_20260816"
down_revision = "p1_commercial_agent_registry_20260816"
branch_labels = None
depends_on = None

_CATALOG = (
    (
        "10000000-0000-4000-8000-000000000001",
        "LEAD_PREPARATION",
        "Lead Preparation Agent",
        "Score, research, prepare, and route leads",
        "prepared_lead",
        500,
        None,
        "lead-preparation.v1",
        False,
    ),
    (
        "10000000-0000-4000-8000-000000000002",
        "EMAIL_OUTREACH",
        "Email Outreach Agent",
        "Execute governed outbound email",
        "accepted_send",
        1000,
        None,
        "email-outreach.v1",
        True,
    ),
    (
        "10000000-0000-4000-8000-000000000003",
        "VOICE_CONVERSATION",
        "Voice Conversation Agent",
        "Execute governed outbound voice conversations",
        "call_attempt",
        100,
        1,
        "voice-conversation.v1",
        True,
    ),
    (
        "10000000-0000-4000-8000-000000000004",
        "CHAT_LEAD_CAPTURE",
        "Chat Lead Capture Agent",
        "Qualify and capture conversational leads",
        "completed_conversation",
        500,
        None,
        "chat-lead-capture.v1",
        True,
    ),
    (
        "10000000-0000-4000-8000-000000000005",
        "CAMPAIGN_MANAGER",
        "Campaign Manager Agent",
        "Plan and orchestrate paid channel agents",
        "active_campaign",
        25,
        None,
        "campaign-manager.v1",
        False,
    ),
    (
        "10000000-0000-4000-8000-000000000006",
        "PROPOSAL_DRAFTING",
        "Proposal Creation Agent",
        "Create governed client proposal versions",
        "proposal_version",
        50,
        None,
        "proposal-drafting.v1",
        True,
    ),
    (
        "10000000-0000-4000-8000-000000000007",
        "CALENDAR_SCHEDULER",
        "Calendar Scheduler Agent",
        "Propose, confirm, book, and reconcile meetings",
        "scheduling_workflow",
        100,
        None,
        "calendar-scheduler.v1",
        True,
    ),
    (
        "10000000-0000-4000-8000-000000000008",
        "REVENUE_INTERVENTION",
        "Revenue Intervention Agent",
        "Evaluate and execute governed revenue interventions",
        "evaluated_intervention",
        500,
        None,
        "revenue-intervention.v1",
        True,
    ),
    (
        "10000000-0000-4000-8000-000000000009",
        "SALES_DAY_ASSISTANT",
        "Sales Day Assistant",
        "Autonomously prioritize and arrange seller actions",
        "planned_action",
        100,
        None,
        "sales-day-assistant.v1",
        False,
    ),
)


def upgrade() -> None:
    catalog = sa.table(
        "agent_catalog_definition",
        sa.column("id", sa.Uuid()),
        sa.column("agent_type", sa.String()),
        sa.column("catalog_version", sa.Integer()),
        sa.column("display_name", sa.String()),
        sa.column("sellable_outcome", sa.String()),
        sa.column("lifecycle_status", sa.String()),
        sa.column("default_capacity_metric", sa.String()),
        sa.column("default_capacity_amount", sa.Integer()),
        sa.column("capacity_period", sa.String()),
        sa.column("default_concurrency", sa.Integer()),
        sa.column("required_capabilities", sa.JSON()),
        sa.column("external_side_effects", sa.Boolean()),
        sa.column("configuration_schema_version", sa.String()),
        sa.column("approved_at", sa.DateTime(timezone=True)),
        sa.column("deprecated_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        catalog,
        [
            {
                "id": uuid.UUID(row[0]),
                "agent_type": row[1],
                "catalog_version": 1,
                "display_name": row[2],
                "sellable_outcome": row[3],
                "lifecycle_status": "PUBLISHED",
                "default_capacity_metric": row[4],
                "default_capacity_amount": row[5],
                "capacity_period": "DAY",
                "default_concurrency": row[6],
                "required_capabilities": [],
                "external_side_effects": row[8],
                "configuration_schema_version": row[7],
                "approved_at": now,
                "deprecated_at": None,
                "created_at": now,
            }
            for row in _CATALOG
        ],
    )


def downgrade() -> None:
    ids = [uuid.UUID(row[0]) for row in _CATALOG]
    op.execute(
        sa.text("DELETE FROM agent_catalog_definition WHERE id IN :ids").bindparams(
            sa.bindparam("ids", value=ids, expanding=True)
        )
    )
