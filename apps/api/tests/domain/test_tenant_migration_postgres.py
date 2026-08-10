from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_TENANT_PG_TESTS") != "1",
    reason="requires an upgraded disposable PostgreSQL database",
)


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB,
        autocommit=False,
    )


def test_composite_workspace_fk_locks_parent_and_denies_workspace_move() -> None:
    campaign_id = uuid.uuid4()
    contact_id = uuid.uuid4()
    action_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    with _connect() as setup:
        setup.execute(
            "INSERT INTO campaigns (id,name,status,created_by,workspace_id,created_at,updated_at) VALUES (%s,%s,'draft',%s,'workspace-a',now(),now())",
            (campaign_id, "concurrency", owner_id),
        )
        setup.execute(
            "INSERT INTO contacts (id,workspace_id,email,timezone,tags_json,intent_json,consent_email,consent_voice,do_not_contact,suppressed,created_at) VALUES (%s,'workspace-a',%s,'UTC','[]','[]',false,false,false,false,now())",
            (contact_id, f"{contact_id}@example.com"),
        )
        setup.commit()

    first = _connect()
    second = _connect()
    try:
        first.execute(
            "INSERT INTO action_queue (id,workspace_id,contact_id,campaign_id,action_type,channel,payload,status,retry_count,created_at) VALUES (%s,'workspace-a',%s,%s,'send_email','email','{}','pending',0,now())",
            (action_id, contact_id, campaign_id),
        )
        second.execute("SET LOCAL lock_timeout = '250ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            second.execute(
                "UPDATE contacts SET workspace_id='workspace-b' WHERE id=%s",
                (contact_id,),
            )
        second.rollback()
        first.commit()

        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            second.execute(
                "UPDATE contacts SET workspace_id='workspace-b' WHERE id=%s",
                (contact_id,),
            )
        second.rollback()
    finally:
        first.close()
        second.close()
        with _connect() as cleanup:
            cleanup.execute("DELETE FROM action_queue WHERE id=%s", (action_id,))
            cleanup.execute("DELETE FROM contacts WHERE id=%s", (contact_id,))
            cleanup.execute("DELETE FROM campaigns WHERE id=%s", (campaign_id,))
            cleanup.commit()
