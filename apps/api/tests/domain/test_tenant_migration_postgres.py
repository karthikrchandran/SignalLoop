from __future__ import annotations

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg
import pytest
from fastapi import HTTPException
from sqlmodel import Session, create_engine

from app.core.config import settings
from app.domain.scheduling.service import handle_calendly_booking

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


def test_calendly_first_booking_wins_under_concurrent_distinct_events() -> None:
    campaign_id = uuid.uuid4()
    contact_id = uuid.uuid4()
    signal_id = uuid.uuid4()
    request_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    first_event = f"event-a-{uuid.uuid4()}"
    second_event = f"event-b-{uuid.uuid4()}"
    with _connect() as setup:
        setup.execute(
            "INSERT INTO campaigns (id,name,status,created_by,workspace_id,created_at,updated_at) VALUES (%s,%s,'draft',%s,'workspace-a',now(),now())",
            (campaign_id, "calendly-concurrency", owner_id),
        )
        setup.execute(
            "INSERT INTO contacts (id,workspace_id,email,timezone,tags_json,intent_json,consent_email,consent_voice,do_not_contact,suppressed,created_at) VALUES (%s,'workspace-a',%s,'UTC','[]','[]',false,false,false,false,now())",
            (contact_id, f"{contact_id}@example.com"),
        )
        setup.execute(
            "INSERT INTO signal_events (id,workspace_id,contact_id,campaign_id,channel,signal_type,confidence,source_event_id,created_at) VALUES (%s,'workspace-a',%s,%s,'email','meeting_interest',1.0,%s,now())",
            (signal_id, contact_id, campaign_id, uuid.uuid4()),
        )
        setup.execute(
            "INSERT INTO scheduling_requests (id,workspace_id,contact_id,campaign_id,signal_event_id,status,source,created_at,updated_at) VALUES (%s,'workspace-a',%s,%s,%s,'pending','manual',now(),now())",
            (request_id, contact_id, campaign_id, signal_id),
        )
        setup.commit()

    first = _connect()
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    def attempt_second_booking() -> int:
        with Session(engine) as second:
            try:
                handle_calendly_booking(
                    second,
                    workspace_id="workspace-a",
                    request_id=request_id,
                    calendly_event_id=second_event,
                    meeting_datetime=datetime(2026, 8, 20, tzinfo=timezone.utc),
                )
            except HTTPException as exc:
                return exc.status_code
        return 200

    try:
        first.execute(
            "SELECT id FROM scheduling_requests WHERE id=%s FOR UPDATE",
            (request_id,),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(attempt_second_booking)
            time.sleep(0.15)
            assert not pending.done()
            first.execute(
                "UPDATE scheduling_requests SET status='booked',calendly_event_id=%s,meeting_datetime=now() WHERE id=%s",
                (first_event, request_id),
            )
            first.commit()
            assert pending.result(timeout=5) == 409

        with Session(engine) as replay:
            booked = handle_calendly_booking(
                replay,
                workspace_id="workspace-a",
                request_id=request_id,
                calendly_event_id=first_event,
                meeting_datetime=datetime(2026, 8, 20, tzinfo=timezone.utc),
            )
            assert booked.calendly_event_id == first_event
    finally:
        first.close()
        engine.dispose()
        with _connect() as cleanup:
            cleanup.execute("DELETE FROM scheduling_requests WHERE id=%s", (request_id,))
            cleanup.execute("DELETE FROM signal_events WHERE id=%s", (signal_id,))
            cleanup.execute("DELETE FROM contacts WHERE id=%s", (contact_id,))
            cleanup.execute("DELETE FROM campaigns WHERE id=%s", (campaign_id,))
            cleanup.commit()
