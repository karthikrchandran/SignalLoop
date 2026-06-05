"""add_workspace_provider_selection_and_capability_enums

Revision ID: m8b9c0d1e2f3
Revises: l7a8b9c0d1e2
Create Date: 2026-06-04 00:00:00.000000

Adds the per-workspace ``workspace_provider_selections`` table that lets a
workspace opt out of the default provider for a given capability
(email/sms/voice/stt/tts/llm) and route to an alternate.  Also extends the
existing ``notificationprovider`` Postgres enum with the new provider values
introduced for the multi-provider story and creates a new
``providercapability`` enum used by the new table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m8b9c0d1e2f3"
down_revision: str | tuple[str, ...] | None = "l7a8b9c0d1e2"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


# New values to append to the existing ``notificationprovider`` enum.
NEW_PROVIDER_VALUES: tuple[str, ...] = (
    "smtp",
    "ses",
    "postmark",
    "mailgun",
    "brevo",
    "resend",
    "deepgram",
    "whisper_api",
    "faster_whisper_local",
    "aura",
    "elevenlabs",
    "playht",
    "polly",
    "piper_local",
    "coqui_local",
    "groq",
    "openai",
    "anthropic",
    "ollama_local",
    "together",
    "openrouter",
    "gemini",
)

CAPABILITY_VALUES: tuple[str, ...] = (
    "email",
    "sms",
    "voice",
    "stt",
    "tts",
    "llm",
)


def upgrade() -> None:
    """Apply this Alembic migration."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ------------------------------------------------------------------
    # 1. Extend the ``notificationprovider`` enum with the new values.
    # ------------------------------------------------------------------
    if dialect == "postgresql":
        # ``ALTER TYPE ... ADD VALUE`` must run outside a transaction block.
        with op.get_context().autocommit_block():
            for value in NEW_PROVIDER_VALUES:
                op.execute(
                    sa.text(
                        f"ALTER TYPE notificationprovider "
                        f"ADD VALUE IF NOT EXISTS '{value}'"
                    )
                )

        # ------------------------------------------------------------------
        # 2. Create the ``providercapability`` enum type.
        # ------------------------------------------------------------------
        provider_capability = postgresql.ENUM(
            *CAPABILITY_VALUES,
            name="providercapability",
            create_type=False,
        )
        provider_capability.create(bind, checkfirst=True)
    else:
        provider_capability = sa.Enum(
            *CAPABILITY_VALUES, name="providercapability"
        )

    # ------------------------------------------------------------------
    # 3. Create the ``workspace_provider_selections`` table.
    # ------------------------------------------------------------------
    op.create_table(
        "workspace_provider_selections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column(
            "capability",
            postgresql.ENUM(
                *CAPABILITY_VALUES,
                name="providercapability",
                create_type=False,
            )
            if dialect == "postgresql"
            else sa.Enum(*CAPABILITY_VALUES, name="providercapability"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            postgresql.ENUM(
                name="notificationprovider", create_type=False
            )
            if dialect == "postgresql"
            else sa.String(length=64),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "capability",
            name="uq_workspace_provider_selection_capability",
        ),
    )
    op.create_index(
        "idx_wps_workspace",
        "workspace_provider_selections",
        ["workspace_id"],
    )


def downgrade() -> None:
    """Revert this Alembic migration."""
    op.drop_index("idx_wps_workspace", table_name="workspace_provider_selections")
    op.drop_table("workspace_provider_selections")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS providercapability"))
        # Note: we intentionally do NOT remove the new values from the
        # ``notificationprovider`` enum.  Postgres does not support dropping
        # enum values cleanly, and downstream rows may already reference them.
