from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from starlette.websockets import WebSocketDisconnect

from app.api.routes import voice as voice_routes
from app.core.config import settings
from app.core.encryption import encrypt
from app.domain.voice.correlation import mint_correlation_token, token_hash
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
    VoiceScript,
)
from app.domain_models import (
    Campaign,
    Contact,
    ContactPublic,
    NotificationProvider,
    ProviderCredential,
    ProviderEventLog,
)
from app.infrastructure.providers.twilio_voice import TwilioVoiceAdapter

WORKSPACE_ID = "ws-voice-tests"
GLOBAL_ACCOUNT_SID = "ACglobalvoice0000000000000000000000"
GLOBAL_AUTH_TOKEN = "global-auth-token"
TENANT_ACCOUNT_SID = "ACtenantvoice0000000000000000000000"
TENANT_AUTH_TOKEN = "tenant-auth-token"
CROSS_ACCOUNT_SID = "ACcrossvoice00000000000000000000000"
CROSS_AUTH_TOKEN = "cross-auth-token"


def _twilio_signature(url: str, params: dict[str, str], auth_token: str) -> str:
    data = url + "".join(f"{key}{value}" for key, value in sorted(params.items()))
    digest = hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _signed_headers(path: str, params: dict[str, str], auth_token: str) -> dict[str, str]:
    url = f"http://testserver{path}"
    return {"X-Twilio-Signature": _twilio_signature(url, params, auth_token)}


def _media_token(call_sid: str, account_sid: str) -> str:
    subject = f"{account_sid}:{call_sid}"
    return hmac.new(
        settings.SECRET_KEY.encode(),
        subject.encode(),
        hashlib.sha256,
    ).hexdigest()


def _call_sid() -> str:
    return f"CA{uuid.uuid4().hex}"


def _seed_call(
    db: Session,
    *,
    call_sid: str = "CAvoicecallback00000000000000000001",
    account_sid: str = GLOBAL_ACCOUNT_SID,
) -> tuple[CallRequest, CallSession]:
    owner_id = uuid.uuid4()
    campaign = Campaign(
        name=f"Voice Campaign {uuid.uuid4()}",
        created_by=owner_id,
        workspace_id=WORKSPACE_ID,
    )
    db.add(campaign)
    db.flush()

    contact = Contact(
        workspace_id=WORKSPACE_ID,
        email=f"voice-{uuid.uuid4()}@example.com",
        first_name="Avery",
        company="ExampleCo",
        phone="+15551234567",
    )
    db.add(contact)
    db.flush()

    script = VoiceScript(
        workspace_id=WORKSPACE_ID,
        campaign_id=campaign.id,
        name="Voice Script",
        content="Say hello and ask one qualifying question.",
        created_by=owner_id,
    )
    db.add(script)
    db.flush()

    call_request = CallRequest(
        workspace_id=WORKSPACE_ID,
        contact_id=contact.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual_queue",
        scheduled_at=datetime.now(timezone.utc),
    )
    db.add(call_request)
    db.flush()

    call_session = CallSession(
        call_request_id=call_request.id,
        twilio_call_sid=call_sid,
        twilio_account_sid=account_sid,
    )
    db.add(call_session)
    db.commit()
    db.refresh(call_request)
    db.refresh(call_session)
    return call_request, call_session


@pytest.fixture(autouse=True)
def twilio_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", GLOBAL_ACCOUNT_SID)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", GLOBAL_AUTH_TOKEN)
    monkeypatch.setattr(settings, "DEFAULT_WORKSPACE_ID", WORKSPACE_ID)
    monkeypatch.setattr(settings, "SERVER_HOST", "testserver")


def test_twilio_callbacks_reject_unsigned_requests(client: TestClient) -> None:
    path = f"{settings.API_V1_STR}/voice/status"
    response = client.post(
        path,
        data={
            "CallSid": "CAunsigned",
            "AccountSid": GLOBAL_ACCOUNT_SID,
            "CallStatus": "ringing",
        },
    )

    assert response.status_code == 403


def test_status_callback_verifies_tenant_credentials_and_is_idempotent(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "wrong-global-token")
    call_sid = _call_sid()
    call_request, call_session = _seed_call(
        db,
        call_sid=call_sid,
        account_sid=TENANT_ACCOUNT_SID,
    )
    db.add(
        ProviderCredential(
            workspace_id=WORKSPACE_ID,
            provider=NotificationProvider.twilio,
            channel="voice",
            encrypted_api_key=encrypt(TENANT_ACCOUNT_SID),
            encrypted_api_secret=encrypt(TENANT_AUTH_TOKEN),
            config_json={"account_sid": TENANT_ACCOUNT_SID},
            is_active=True,
        )
    )
    db.commit()

    path = f"{settings.API_V1_STR}/voice/status"
    ringing_params = {
        "CallSid": call_session.twilio_call_sid,
        "AccountSid": TENANT_ACCOUNT_SID,
        "CallStatus": "ringing",
    }
    response = client.post(
        path,
        data=ringing_params,
        headers=_signed_headers(path, ringing_params, TENANT_AUTH_TOKEN),
    )

    assert response.status_code == 200
    db.refresh(call_request)
    db.refresh(call_session)
    assert call_request.status == CallRequestStatus.in_progress
    assert call_session.twilio_status == "ringing"

    duplicate_response = client.post(
        path,
        data=ringing_params,
        headers=_signed_headers(path, ringing_params, TENANT_AUTH_TOKEN),
    )

    assert duplicate_response.status_code == 200
    assert duplicate_response.json() == {"status": "ignored"}

    stale_params = {
        "CallSid": call_session.twilio_call_sid,
        "AccountSid": TENANT_ACCOUNT_SID,
        "CallStatus": "initiated",
    }
    stale_response = client.post(
        path,
        data=stale_params,
        headers=_signed_headers(path, stale_params, TENANT_AUTH_TOKEN),
    )

    assert stale_response.status_code == 200
    db.refresh(call_session)
    assert call_session.twilio_status == "ringing"
    events = db.exec(
        select(ProviderEventLog).where(
            ProviderEventLog.provider == NotificationProvider.twilio,
        )
    ).all()
    assert len(events) >= 2


def test_status_callback_detects_voicemail(client: TestClient, db: Session) -> None:
    call_request, call_session = _seed_call(db, call_sid=_call_sid())
    path = f"{settings.API_V1_STR}/voice/status"
    params = {
        "CallSid": call_session.twilio_call_sid,
        "AccountSid": GLOBAL_ACCOUNT_SID,
        "CallStatus": "in-progress",
        "AnsweredBy": "machine_start",
    }

    response = client.post(path, data=params, headers=_signed_headers(path, params, GLOBAL_AUTH_TOKEN))

    assert response.status_code == 200
    db.refresh(call_request)
    db.refresh(call_session)
    assert call_session.outcome == CallOutcome.voicemail
    assert call_request.status == CallRequestStatus.completed


def test_recording_callback_persists_recording_url(client: TestClient, db: Session) -> None:
    _, call_session = _seed_call(db, call_sid=_call_sid())
    path = f"{settings.API_V1_STR}/voice/recording"
    params = {
        "CallSid": call_session.twilio_call_sid,
        "AccountSid": GLOBAL_ACCOUNT_SID,
        "RecordingUrl": "https://api.twilio.com/recordings/RE123",
    }

    response = client.post(path, data=params, headers=_signed_headers(path, params, GLOBAL_AUTH_TOKEN))

    assert response.status_code == 200
    db.refresh(call_session)
    assert call_session.recording_url == params["RecordingUrl"]

    duplicate_response = client.post(
        path,
        data=params,
        headers=_signed_headers(path, params, GLOBAL_AUTH_TOKEN),
    )

    assert duplicate_response.status_code == 200
    assert duplicate_response.json() == {"status": "ignored"}


@pytest.mark.parametrize("endpoint", ["twiml", "status", "recording"])
def test_twilio_endpoints_reject_signed_cross_account_call_attachment(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    call_request, call_session = _seed_call(db, call_sid=_call_sid())
    db.add(
        ProviderCredential(
            workspace_id="workspace-b",
            provider=NotificationProvider.twilio,
            channel="voice",
            encrypted_api_key=encrypt(CROSS_ACCOUNT_SID),
            encrypted_api_secret=encrypt(CROSS_AUTH_TOKEN),
            config_json={"account_sid": CROSS_ACCOUNT_SID},
            is_active=True,
        )
    )
    db.commit()
    credential_reads: list[uuid.UUID] = []
    original_decrypt = voice_routes._decrypt_twilio_credential

    def capture_credential_read(row: ProviderCredential) -> tuple[str, str]:
        credential_reads.append(row.id)
        return original_decrypt(row)

    monkeypatch.setattr(
        voice_routes, "_decrypt_twilio_credential", capture_credential_read
    )
    path = f"{settings.API_V1_STR}/voice/{endpoint}"
    params = {
        "CallSid": call_session.twilio_call_sid,
        "AccountSid": CROSS_ACCOUNT_SID,
    }
    if endpoint == "status":
        params["CallStatus"] = "completed"
    if endpoint == "recording":
        params["RecordingUrl"] = "https://api.twilio.com/recordings/cross"
    event_ids_before = {
        event.id for event in db.exec(select(ProviderEventLog)).all()
    }

    response = client.post(
        path,
        data=params,
        headers=_signed_headers(path, params, CROSS_AUTH_TOKEN),
    )

    assert response.status_code == 403
    assert credential_reads == []
    db.refresh(call_request)
    db.refresh(call_session)
    assert call_session.twilio_account_sid == GLOBAL_ACCOUNT_SID
    assert call_session.twilio_status is None
    assert call_session.recording_url is None
    assert call_request.status == CallRequestStatus.queued
    assert {
        event.id for event in db.exec(select(ProviderEventLog)).all()
    } == event_ids_before


def test_status_callback_atomically_binds_first_sid_from_precommitted_correlation(
    client: TestClient,
    db: Session,
) -> None:
    call_request, call_session = _seed_call(db, call_sid="")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    correlation = mint_correlation_token(
        call_session.id,
        settings.SECRET_KEY,
        expires_at=int(expires_at.timestamp()),
    )
    call_session.callback_correlation_hash = token_hash(correlation)
    call_session.callback_correlation_expires_at = expires_at
    call_session.twilio_status = "initiating"
    db.add(call_session)
    db.commit()

    call_sid = _call_sid()
    path = f"{settings.API_V1_STR}/voice/status?correlation={correlation}"
    params = {
        "CallSid": call_sid,
        "AccountSid": GLOBAL_ACCOUNT_SID,
        "CallStatus": "ringing",
    }
    response = client.post(
        path,
        data=params,
        headers=_signed_headers(path, params, GLOBAL_AUTH_TOKEN),
    )

    assert response.status_code == 200
    db.refresh(call_request)
    db.refresh(call_session)
    assert call_session.twilio_call_sid == call_sid
    assert call_request.status == CallRequestStatus.in_progress

    attacker_sid = _call_sid()
    attacker_params = {**params, "CallSid": attacker_sid}
    attacker = client.post(
        path,
        data=attacker_params,
        headers=_signed_headers(path, attacker_params, GLOBAL_AUTH_TOKEN),
    )
    assert attacker.status_code == 403
    db.refresh(call_session)
    assert call_session.twilio_call_sid == call_sid


def test_twilio_callback_rejects_missing_stored_account_binding(
    client: TestClient,
    db: Session,
) -> None:
    call_request, call_session = _seed_call(db, call_sid=_call_sid())
    call_session.twilio_account_sid = None
    db.add(call_session)
    db.commit()
    path = f"{settings.API_V1_STR}/voice/status"
    params = {
        "CallSid": call_session.twilio_call_sid,
        "AccountSid": GLOBAL_ACCOUNT_SID,
        "CallStatus": "completed",
    }

    response = client.post(
        path,
        data=params,
        headers=_signed_headers(path, params, GLOBAL_AUTH_TOKEN),
    )

    assert response.status_code == 403
    db.refresh(call_request)
    db.refresh(call_session)
    assert call_session.twilio_account_sid is None
    assert call_session.twilio_status is None
    assert call_request.status == CallRequestStatus.queued


def test_adapter_enables_machine_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, url: str, *, data: dict[str, str], auth: tuple[str, str]) -> httpx.Response:
            captured["data"] = data
            captured["auth"] = auth
            return httpx.Response(201, json={"sid": "CAcreated", "status": "queued"})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    adapter = TwilioVoiceAdapter(
        account_sid=GLOBAL_ACCOUNT_SID,
        auth_token=GLOBAL_AUTH_TOKEN,
        from_number="+15550000000",
    )

    result = asyncio.run(
        adapter.initiate_call(
            to="+15551234567",
            twiml_url="https://api.example.test/voice/twiml",
            status_callback_url="https://api.example.test/voice/status",
        )
    )

    assert result == {"call_sid": "CAcreated", "status": "queued"}
    assert captured["data"]["MachineDetection"] == "Enable"
    assert captured["data"]["RecordingStatusCallback"].endswith("/voice/recording")


def test_adapter_sanitizes_twilio_error_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, url: str, *, data: dict[str, str], auth: tuple[str, str]) -> httpx.Response:
            return httpx.Response(
                400,
                json={"code": 21211, "message": "Invalid To number +15551234567"},
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    adapter = TwilioVoiceAdapter(
        account_sid=GLOBAL_ACCOUNT_SID,
        auth_token=GLOBAL_AUTH_TOKEN,
        from_number="+15550000000",
    )

    result = asyncio.run(
        adapter.initiate_call(
            to="+15551234567",
            twiml_url="https://api.example.test/voice/twiml",
            status_callback_url="https://api.example.test/voice/status",
        )
    )

    assert result == {
        "call_sid": "",
        "status": "failed",
        "error": "twilio_call_failed",
        "error_code": "21211",
    }
    assert "+15551234567" not in str(result)


def test_twiml_includes_authenticated_media_stream_metadata(
    client: TestClient,
    db: Session,
) -> None:
    call_sid = _call_sid()
    _, call_session = _seed_call(db, call_sid=call_sid)
    path = f"{settings.API_V1_STR}/voice/twiml"
    params = {
        "CallSid": call_sid,
        "AccountSid": GLOBAL_ACCOUNT_SID,
    }

    response = client.post(path, data=params, headers=_signed_headers(path, params, GLOBAL_AUTH_TOKEN))

    assert response.status_code == 200
    body = response.text
    assert '<Stream url="ws://testserver/api/v1/voice/media-stream?' in body
    assert f'<Parameter name="call_sid" value="{call_sid}" />' in body
    assert '<Parameter name="account_sid" value="ACglobalvoice0000000000000000000000" />' in body

    stream_url = html.unescape(body.split('<Stream url="', 1)[1].split('">', 1)[0])
    query = parse_qs(urlparse(stream_url).query)
    assert query["call_sid"] == [call_sid]
    assert query["account_sid"] == [GLOBAL_ACCOUNT_SID]
    assert query["token"] != [_media_token(call_sid, GLOBAL_ACCOUNT_SID)]
    db.refresh(call_session)
    assert call_session.media_stream_nonce_hash == voice_routes._token_hash(query["token"][0])
    assert call_session.media_stream_token_expires_at is not None


def test_media_stream_rejects_mismatched_start_frame(client: TestClient, db: Session) -> None:
    call_sid = _call_sid()
    _seed_call(db, call_sid=call_sid)
    twiml_path = f"{settings.API_V1_STR}/voice/twiml"
    params = {"CallSid": call_sid, "AccountSid": GLOBAL_ACCOUNT_SID}
    response = client.post(twiml_path, data=params, headers=_signed_headers(twiml_path, params, GLOBAL_AUTH_TOKEN))
    stream_url = html.unescape(response.text.split('<Stream url="', 1)[1].split('">', 1)[0])
    path = stream_url.replace("ws://testserver", "")

    with client.websocket_connect(path) as websocket:
        websocket.send_json(
            {
                "event": "start",
                "start": {
                    "callSid": "CAother000000000000000000000001",
                    "accountSid": GLOBAL_ACCOUNT_SID,
                    "streamSid": "MSstream0000000000000000000001",
                    "customParameters": {},
                },
            }
        )
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_text()

    assert exc_info.value.code == 1008


def test_media_stream_binds_account_when_loading_call(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_sid = _call_sid()
    _seed_call(db, call_sid=call_sid)
    loader = AsyncMock(return_value=None)
    monkeypatch.setattr(voice_routes, "_load_engine_for_call", loader)
    twiml_path = f"{settings.API_V1_STR}/voice/twiml"
    params = {"CallSid": call_sid, "AccountSid": GLOBAL_ACCOUNT_SID}
    response = client.post(twiml_path, data=params, headers=_signed_headers(twiml_path, params, GLOBAL_AUTH_TOKEN))
    stream_url = html.unescape(response.text.split('<Stream url="', 1)[1].split('">', 1)[0])
    path = stream_url.replace("ws://testserver", "")

    with client.websocket_connect(path) as websocket:
        websocket.send_json(
            {
                "event": "start",
                "start": {
                    "callSid": call_sid,
                    "accountSid": GLOBAL_ACCOUNT_SID,
                    "streamSid": "MSstream0000000000000000000002",
                    "customParameters": {},
                },
            }
        )
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_text()

    loader.assert_awaited_once_with(call_sid, GLOBAL_ACCOUNT_SID)


def test_media_stream_nonce_is_one_time(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_sid = _call_sid()
    _seed_call(db, call_sid=call_sid)
    monkeypatch.setattr(voice_routes, "_load_engine_for_call", AsyncMock(return_value=None))
    twiml_path = f"{settings.API_V1_STR}/voice/twiml"
    params = {"CallSid": call_sid, "AccountSid": GLOBAL_ACCOUNT_SID}
    response = client.post(twiml_path, data=params, headers=_signed_headers(twiml_path, params, GLOBAL_AUTH_TOKEN))
    path = html.unescape(response.text.split('<Stream url="', 1)[1].split('">', 1)[0]).replace("ws://testserver", "")

    with client.websocket_connect(path) as websocket:
        websocket.send_json({"event": "start", "start": {"callSid": call_sid, "accountSid": GLOBAL_ACCOUNT_SID, "streamSid": "MS-one", "customParameters": {}}})
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_text()

    with pytest.raises(WebSocketDisconnect) as replay:
        with client.websocket_connect(path):
            pass
    assert replay.value.code == 1008


def test_media_stream_nonce_rejects_expiry_and_terminal_call(
    client: TestClient, db: Session
) -> None:
    for terminal in (False, True):
        call_sid = _call_sid()
        call_request, call_session = _seed_call(db, call_sid=call_sid)
        twiml_path = f"{settings.API_V1_STR}/voice/twiml"
        params = {"CallSid": call_sid, "AccountSid": GLOBAL_ACCOUNT_SID}
        response = client.post(twiml_path, data=params, headers=_signed_headers(twiml_path, params, GLOBAL_AUTH_TOKEN))
        path = html.unescape(response.text.split('<Stream url="', 1)[1].split('">', 1)[0]).replace("ws://testserver", "")
        if terminal:
            call_request.status = CallRequestStatus.completed
            db.add(call_request)
        else:
            call_session.media_stream_token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.add(call_session)
        db.commit()

        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect(path):
                pass
        assert rejected.value.code == 1008


def test_save_conversation_results_rejects_cross_account(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, call_session = _seed_call(db, call_sid=_call_sid())
    engine_state = SimpleNamespace(
        messages=[{"role": "user", "content": "tenant-b transcript"}],
        unanswered_questions=[],
        scheduling_interest=False,
    )
    conversation_engine = SimpleNamespace(state=engine_state)

    class _SessionContext:
        def __enter__(self) -> Session:
            return db

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(voice_routes, "Session", lambda _engine: _SessionContext())

    voice_routes._save_conversation_results(
        call_session.twilio_call_sid,
        CROSS_ACCOUNT_SID,
        conversation_engine,
    )

    db.refresh(call_session)
    assert call_session.transcript is None


def test_load_engine_for_call_rejects_missing_campaign_without_adapter_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(voice_routes.settings, "USE_ECRM_SHARED_RECORDS", True)
    contact_id = uuid.uuid4()

    class _DummyAdapter:
        pass

    monkeypatch.setattr(
        voice_routes, "resolve_stt_adapter", lambda *args, **kwargs: _DummyAdapter()
    )
    monkeypatch.setattr(
        voice_routes, "resolve_tts_adapter", lambda *args, **kwargs: _DummyAdapter()
    )
    monkeypatch.setattr(
        voice_routes, "resolve_llm_adapter", lambda *args, **kwargs: _DummyAdapter()
    )
    requested_workspaces: list[str] = []

    def get_shared_contact(*, workspace_id: str, contact_id: uuid.UUID) -> ContactPublic:
        requested_workspaces.append(workspace_id)
        return ContactPublic(
            id=contact_id,
            workspace_id=WORKSPACE_ID,
            account_id=None,
            email="voice@example.com",
            first_name="Avery",
            last_name="Stone",
            company="SharedCo",
            phone="+15551234567",
            timezone="UTC",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(
        voice_routes.shared_record_service,
        "get_shared_contact",
        get_shared_contact,
    )
    monkeypatch.setattr(
        voice_routes,
        "resolve_workspace_runtime_config",
        lambda *args, **kwargs: SimpleNamespace(
            deepgram_api_key=SimpleNamespace(value=""),
            groq_api_key=SimpleNamespace(value=""),
            team_notification_email=SimpleNamespace(value=""),
        ),
    )

    owner_id = uuid.uuid4()
    campaign = Campaign(
        name="Voice",
        workspace_id=WORKSPACE_ID,
        created_by=owner_id,
    )
    script = VoiceScript(
        campaign_id=campaign.id,
        name="Voice Script",
        content="Say hello.",
        created_by=owner_id,
    )
    call_request = CallRequest(
        workspace_id=WORKSPACE_ID,
        contact_id=contact_id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual_queue",
        scheduled_at=datetime.now(timezone.utc),
    )
    call_session = CallSession(
        call_request_id=call_request.id,
        twilio_call_sid=_call_sid(),
        twilio_account_sid=GLOBAL_ACCOUNT_SID,
    )

    class _FakeResult:
        def __init__(self, value: object) -> None:
            self._value = value

        def first(self) -> object:
            return self._value

    class _FakeSession:
        def __enter__(self) -> _FakeSession:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def exec(self, statement):  # type: ignore[no-untyped-def]
            entity = statement.column_descriptions[0]["entity"]
            if entity is voice_routes.CallSession:
                return _FakeResult(call_session)
            if entity is voice_routes.CallRequest:
                return _FakeResult(call_request)
            if entity is voice_routes.VoiceScript:
                return _FakeResult(script)
            if entity is voice_routes.Campaign:
                return _FakeResult(campaign)
            return _FakeResult(None)

        def get(self, model, key):  # type: ignore[no-untyped-def]
            if model is voice_routes.CallRequest and key == call_request.id:
                return call_request
            if model is voice_routes.VoiceScript and key == script.id:
                return script
            if model is voice_routes.Campaign and key == campaign.id:
                return None
            return None

    monkeypatch.setattr(voice_routes, "Session", lambda *args, **kwargs: _FakeSession())

    engine = asyncio.run(
        voice_routes._load_engine_for_call(
            call_session.twilio_call_sid,
            GLOBAL_ACCOUNT_SID,
        )
    )

    assert engine is None
    assert requested_workspaces == []


def test_parent_campaign_workspace_move_is_denied_by_relational_constraint(
    db: Session,
) -> None:
    call_request, _call_session = _seed_call(db, call_sid=_call_sid())
    campaign = db.get(Campaign, call_request.campaign_id)
    assert campaign is not None
    campaign.workspace_id = "workspace-b"
    db.add(campaign)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
