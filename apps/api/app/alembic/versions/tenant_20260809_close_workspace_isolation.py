"""close workspace isolation for suppression and dispatch jobs

Revision ID: tenant_20260809
Revises: psid_20260726
Create Date: 2026-08-09 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "tenant_20260809"
down_revision: str | None = "psid_20260726"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

def _add_workspace_column(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column(
            "workspace_id",
            sa.String(length=64),
            nullable=True,
        ),
    )


def _finish_workspace_column(table_name: str, index_name: str) -> None:
    op.alter_column(
        table_name,
        "workspace_id",
        existing_type=sa.String(length=64),
        nullable=False,
        server_default=None,
    )
    op.create_index(index_name, table_name, ["workspace_id"])


def _preflight_or_raise(
    connection: Connection, label: str, count_sql: str
) -> None:
    count = int(connection.execute(sa.text(count_sql)).scalar_one())
    if count:
        raise RuntimeError(f"{label}: {count} inconsistent row(s)")


def _preflight_source_chains() -> None:
    connection = op.get_bind()
    checks = (
        (
            "unattributable email suppression ownership",
            "SELECT count(*) FROM email_suppressions",
        ),
        (
            "inconsistent call request ownership",
            """SELECT count(*) FROM call_requests cr
            LEFT JOIN campaigns c ON c.id = cr.campaign_id
            LEFT JOIN voice_scripts vs ON vs.id = cr.voice_script_id
            LEFT JOIN contacts contact ON contact.id = cr.contact_id
            WHERE c.id IS NULL OR vs.id IS NULL OR vs.campaign_id <> c.id
               OR contact.id IS NULL OR contact.workspace_id <> c.workspace_id""",
        ),
        (
            "inconsistent action queue ownership",
            """SELECT count(*) FROM action_queue aq
            LEFT JOIN campaigns c ON c.id = aq.campaign_id
            LEFT JOIN contacts contact ON contact.id = aq.contact_id
            WHERE c.id IS NULL OR contact.id IS NULL
               OR contact.workspace_id <> c.workspace_id""",
        ),
        (
            "inconsistent send request ownership",
            """SELECT count(*) FROM send_requests sr
            LEFT JOIN contact_sequence_state css ON css.id = sr.contact_sequence_state_id
            LEFT JOIN email_sequences es ON es.id = css.sequence_id
            LEFT JOIN campaigns c ON c.id = es.campaign_id
            LEFT JOIN contacts contact ON contact.id = css.contact_id
            WHERE css.id IS NULL OR es.id IS NULL OR c.id IS NULL
               OR contact.id IS NULL OR contact.workspace_id <> c.workspace_id""",
        ),
        (
            "unattributable outbox ownership",
            """SELECT count(*) FROM outbox_events
            WHERE coalesce(event_data ->> 'workspace_id', '') = ''""",
        ),
        (
            "inconsistent signal ownership",
            """SELECT count(*) FROM signal_events se
            LEFT JOIN campaigns c ON c.id = se.campaign_id
            LEFT JOIN contacts contact ON contact.id = se.contact_id
            WHERE c.id IS NULL OR contact.id IS NULL
               OR contact.workspace_id <> c.workspace_id""",
        ),
        (
            "inconsistent scheduling ownership",
            """SELECT count(*) FROM scheduling_requests sr
            LEFT JOIN campaigns c ON c.id = sr.campaign_id
            LEFT JOIN signal_events se ON se.id = sr.signal_event_id
            LEFT JOIN contacts contact ON contact.id = sr.contact_id
            WHERE c.id IS NULL OR contact.id IS NULL
               OR contact.workspace_id <> c.workspace_id
               OR (se.id IS NOT NULL AND se.campaign_id <> c.id)""",
        ),
    )
    for label, sql in checks:
        _preflight_or_raise(connection, label, sql)


def upgrade() -> None:
    """Anchor dispatch, suppression, replay, and retry state to a workspace."""
    _preflight_source_chains()

    for column_name in (
        "consent_email",
        "consent_voice",
        "do_not_contact",
        "suppressed",
    ):
        op.add_column(
            "contacts",
            sa.Column(column_name, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("contacts", column_name, server_default=None)

    _add_workspace_column("email_suppressions")
    _finish_workspace_column(
        "email_suppressions",
        "ix_email_suppressions_workspace_id",
    )
    op.drop_constraint(
        "uq_suppression_email_reason",
        "email_suppressions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_suppression_workspace_email_reason",
        "email_suppressions",
        ["workspace_id", "email", "reason"],
    )

    _add_workspace_column("call_requests")
    op.execute(
        sa.text(
            """
            UPDATE call_requests AS call_request
            SET workspace_id = campaign.workspace_id
            FROM campaigns AS campaign
            WHERE campaign.id = call_request.campaign_id
            """
        )
    )
    _finish_workspace_column("call_requests", "ix_call_requests_workspace_id")

    _add_workspace_column("action_queue")
    op.execute(
        sa.text(
            """
            UPDATE action_queue AS action
            SET workspace_id = campaign.workspace_id
            FROM campaigns AS campaign
            WHERE campaign.id = action.campaign_id
            """
        )
    )
    _finish_workspace_column("action_queue", "ix_action_queue_workspace_id")

    _add_workspace_column("send_requests")
    op.execute(
        sa.text(
            """
            UPDATE send_requests AS send_request
            SET workspace_id = campaign.workspace_id
            FROM contact_sequence_state AS state
            JOIN email_sequences AS sequence ON sequence.id = state.sequence_id
            JOIN campaigns AS campaign ON campaign.id = sequence.campaign_id
            WHERE state.id = send_request.contact_sequence_state_id
            """
        )
    )
    _finish_workspace_column("send_requests", "ix_send_requests_workspace_id")
    op.create_index(
        "ix_send_requests_idempotency_key",
        "send_requests",
        ["idempotency_key"],
    )
    op.drop_constraint(
        "uq_send_request_idempotency_key",
        "send_requests",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_send_request_workspace_idempotency",
        "send_requests",
        ["workspace_id", "idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_send_request_workspace_provider_message",
        "send_requests",
        ["workspace_id", "provider_message_id"],
    )

    op.drop_constraint(
        "uq_provider_event_provider_event_id",
        "provider_event_logs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_provider_event_workspace_provider_event_id",
        "provider_event_logs",
        ["workspace_id", "provider", "provider_event_id"],
    )

    _add_workspace_column("outbox_events")
    op.execute(
        sa.text(
            "UPDATE outbox_events SET workspace_id = event_data ->> 'workspace_id'"
        )
    )
    _finish_workspace_column("outbox_events", "ix_outbox_events_workspace_id")
    op.drop_constraint("uq_outbox_idempotency_key", "outbox_events", type_="unique")
    op.create_unique_constraint(
        "uq_outbox_workspace_idempotency",
        "outbox_events",
        ["workspace_id", "idempotency_key"],
    )

    _add_workspace_column("signal_events")
    op.execute(
        sa.text(
            """UPDATE signal_events AS signal
            SET workspace_id = campaign.workspace_id
            FROM campaigns AS campaign
            WHERE campaign.id = signal.campaign_id"""
        )
    )
    _finish_workspace_column("signal_events", "ix_signal_events_workspace_id")
    op.create_unique_constraint(
        "uq_signal_workspace_source_type",
        "signal_events",
        ["workspace_id", "source_event_id", "signal_type"],
    )

    _add_workspace_column("scheduling_requests")
    op.execute(
        sa.text(
            """UPDATE scheduling_requests AS request
            SET workspace_id = campaign.workspace_id
            FROM campaigns AS campaign
            WHERE campaign.id = request.campaign_id"""
        )
    )
    _finish_workspace_column(
        "scheduling_requests", "ix_scheduling_requests_workspace_id"
    )
    op.create_unique_constraint(
        "uq_scheduling_workspace_signal",
        "scheduling_requests",
        ["workspace_id", "signal_event_id"],
    )

    op.execute(
        sa.text(
            """CREATE FUNCTION enforce_campaign_workspace() RETURNS trigger AS $$
            DECLARE owner_workspace varchar(64);
            BEGIN
              SELECT workspace_id INTO owner_workspace FROM campaigns WHERE id = NEW.campaign_id;
              IF owner_workspace IS NULL OR owner_workspace <> NEW.workspace_id THEN
                RAISE EXCEPTION 'workspace mismatch for % campaign %', TG_TABLE_NAME, NEW.campaign_id;
              END IF;
              IF NOT EXISTS (
                SELECT 1 FROM contacts
                WHERE id = NEW.contact_id AND workspace_id = NEW.workspace_id
              ) THEN
                RAISE EXCEPTION 'contact workspace mismatch for % contact %', TG_TABLE_NAME, NEW.contact_id;
              END IF;
              IF TG_TABLE_NAME = 'call_requests' THEN
                IF NOT EXISTS (
                  SELECT 1 FROM voice_scripts
                  WHERE id = NEW.voice_script_id AND campaign_id = NEW.campaign_id
                ) THEN
                  RAISE EXCEPTION 'voice script campaign mismatch for call request %', NEW.id;
                END IF;
              END IF;
              IF TG_TABLE_NAME = 'scheduling_requests' THEN
                IF NEW.signal_event_id IS NOT NULL AND NOT EXISTS (
                  SELECT 1 FROM signal_events
                  WHERE id = NEW.signal_event_id
                    AND campaign_id = NEW.campaign_id
                    AND workspace_id = NEW.workspace_id
                ) THEN
                  RAISE EXCEPTION 'signal workspace mismatch for scheduling request %', NEW.id;
                END IF;
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql"""
        )
    )
    for table_name in (
        "call_requests",
        "action_queue",
        "signal_events",
        "scheduling_requests",
    ):
        op.execute(
            sa.text(
                f"""CREATE CONSTRAINT TRIGGER ck_{table_name}_workspace
                AFTER INSERT OR UPDATE ON {table_name}
                DEFERRABLE INITIALLY IMMEDIATE
                FOR EACH ROW EXECUTE FUNCTION enforce_campaign_workspace()"""
            )
        )

    op.execute(
        sa.text(
            """CREATE FUNCTION enforce_send_request_workspace() RETURNS trigger AS $$
            DECLARE owner_workspace varchar(64); contact_workspace varchar(64);
            BEGIN
              SELECT c.workspace_id, contact.workspace_id
              INTO owner_workspace, contact_workspace
              FROM contact_sequence_state css
              JOIN email_sequences es ON es.id = css.sequence_id
              JOIN campaigns c ON c.id = es.campaign_id
              JOIN contacts contact ON contact.id = css.contact_id
              WHERE css.id = NEW.contact_sequence_state_id;
              IF owner_workspace IS NULL OR owner_workspace <> NEW.workspace_id
                 OR contact_workspace IS NULL OR contact_workspace <> NEW.workspace_id THEN
                RAISE EXCEPTION 'workspace mismatch for send request %', NEW.id;
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql"""
        )
    )
    op.execute(
        sa.text(
            """CREATE CONSTRAINT TRIGGER ck_send_requests_workspace
            AFTER INSERT OR UPDATE ON send_requests
            DEFERRABLE INITIALLY IMMEDIATE
            FOR EACH ROW EXECUTE FUNCTION enforce_send_request_workspace()"""
        )
    )


def downgrade() -> None:
    """Restore the pre-isolation schema when no cross-workspace duplicates exist."""
    op.execute("DROP TRIGGER IF EXISTS ck_send_requests_workspace ON send_requests")
    op.execute("DROP FUNCTION IF EXISTS enforce_send_request_workspace()")
    for table_name in (
        "call_requests",
        "action_queue",
        "signal_events",
        "scheduling_requests",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS ck_{table_name}_workspace ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS enforce_campaign_workspace()")

    op.drop_constraint(
        "uq_scheduling_workspace_signal", "scheduling_requests", type_="unique"
    )
    op.drop_index(
        "ix_scheduling_requests_workspace_id", table_name="scheduling_requests"
    )
    op.drop_column("scheduling_requests", "workspace_id")

    op.drop_constraint(
        "uq_signal_workspace_source_type", "signal_events", type_="unique"
    )
    op.drop_index("ix_signal_events_workspace_id", table_name="signal_events")
    op.drop_column("signal_events", "workspace_id")

    op.drop_constraint(
        "uq_outbox_workspace_idempotency", "outbox_events", type_="unique"
    )
    op.create_unique_constraint(
        "uq_outbox_idempotency_key", "outbox_events", ["idempotency_key"]
    )
    op.drop_index("ix_outbox_events_workspace_id", table_name="outbox_events")
    op.drop_column("outbox_events", "workspace_id")

    op.drop_constraint(
        "uq_provider_event_workspace_provider_event_id",
        "provider_event_logs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_provider_event_provider_event_id",
        "provider_event_logs",
        ["provider", "provider_event_id"],
    )

    op.drop_constraint(
        "uq_send_request_workspace_provider_message",
        "send_requests",
        type_="unique",
    )
    op.drop_constraint(
        "uq_send_request_workspace_idempotency",
        "send_requests",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_send_request_idempotency_key",
        "send_requests",
        ["idempotency_key"],
    )
    op.drop_index("ix_send_requests_idempotency_key", table_name="send_requests")
    op.drop_index("ix_send_requests_workspace_id", table_name="send_requests")
    op.drop_column("send_requests", "workspace_id")

    op.drop_index("ix_call_requests_workspace_id", table_name="call_requests")
    op.drop_column("call_requests", "workspace_id")

    op.drop_index("ix_action_queue_workspace_id", table_name="action_queue")
    op.drop_column("action_queue", "workspace_id")

    op.drop_constraint(
        "uq_suppression_workspace_email_reason",
        "email_suppressions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_suppression_email_reason",
        "email_suppressions",
        ["email", "reason"],
    )
    op.drop_index(
        "ix_email_suppressions_workspace_id",
        table_name="email_suppressions",
    )
    op.drop_column("email_suppressions", "workspace_id")

    for column_name in (
        "suppressed",
        "do_not_contact",
        "consent_voice",
        "consent_email",
    ):
        op.drop_column("contacts", column_name)
