"""Voice call endpoints: TwiML, WebSocket media stream, status/recording callbacks."""
from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
from contextlib import suppress
from datetime import datetime, timezone
from urllib.parse import urlencode
from xml.sax.saxutils import quoteattr

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.db import engine
from app.core.encryption import decrypt
from app.domain.timeline.timeline_service import (
    invalidate_timeline_cache,
    invalidate_timeline_cache_from_url_sync,
)
from app.domain.voice.conversation_engine import ConversationEngine
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
    VoiceScript,
)
from app.domain.voice.script_parser import parse_script
from app.domain_models import Contact, NotificationProvider, ProviderCredential
from app.infrastructure.providers.errors import ProviderConfigurationError
from app.infrastructure.providers.twilio_voice import TwilioVoiceAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])
MEDIA_STREAM_IDLE_TIMEOUT_SECONDS = 10.0
MEDIA_STREAM_MAX_CALL_SECONDS = 30 * 60.0
MEDIA_STREAM_CLOSE_TIMEOUT_SECONDS = 1.0
TTS_FIRST_AUDIO_TIMEOUT_SECONDS = 0.1
RESPONSE_LATENCY_BUDGET_SECONDS = 0.5
MEDIA_TOKEN_QUERY_PARAM = "token"
MEDIA_CALL_QUERY_PARAM = "call_sid"
MEDIA_ACCOUNT_QUERY_PARAM = "account_sid"
TERMINAL_TWILIO_STATUSES = {"busy", "canceled", "completed", "failed", "no-answer"}
ACTIVE_TWILIO_STATUSES = {"answered", "in-progress", "initiated", "ringing"}
TWILIO_STATUS_RANK = {
    "initiated": 10,
    "ringing": 20,
    "answered": 30,
    "in-progress": 40,
    "busy": 100,
    "canceled": 100,
    "completed": 100,
    "failed": 100,
    "no-answer": 100,
}

# Map Twilio call statuses to our outcomes
TWILIO_STATUS_MAP = {
    "completed": CallOutcome.answered,
    "busy": CallOutcome.busy,
    "no-answer": CallOutcome.no_answer,
    "failed": CallOutcome.failed,
    "canceled": CallOutcome.failed,
}


def _verify_twilio_webhook(
    request: Request,
    params: dict[str, str],
    session: Session,
) -> None:
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    url = str(request.url)
    auth_tokens = _twilio_auth_tokens_for_request(session, params)
    if not any(
        TwilioVoiceAdapter.verify_request_signature(
            url,
            params,
            signature,
            auth_token=auth_token,
        )
        for auth_token in auth_tokens
    ):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


def _twilio_auth_tokens_for_request(
    session: Session,
    params: dict[str, str],
) -> list[str]:
    account_sid = params.get("AccountSid", "").strip()
    call_sid = params.get("CallSid", "").strip()
    if not account_sid and call_sid:
        call_session = session.exec(
            select(CallSession).where(CallSession.twilio_call_sid == call_sid)
        ).first()
        account_sid = call_session.twilio_account_sid if call_session else ""

    tokens: list[str] = []
    if account_sid == settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        tokens.append(settings.TWILIO_AUTH_TOKEN)

    if account_sid:
        rows = session.exec(
            select(ProviderCredential).where(
                ProviderCredential.provider == NotificationProvider.twilio,
                ProviderCredential.channel == "voice",
                ProviderCredential.is_active == True,  # noqa: E712
            )
        ).all()
        for row in rows:
            row_account_sid, row_auth_token = _decrypt_twilio_credential(row)
            if row_account_sid == account_sid and row_auth_token:
                tokens.append(row_auth_token)

    if not tokens and not account_sid and settings.TWILIO_AUTH_TOKEN:
        tokens.append(settings.TWILIO_AUTH_TOKEN)
    return list(dict.fromkeys(tokens))


def _decrypt_twilio_credential(row: ProviderCredential) -> tuple[str, str]:
    try:
        account_sid = str(row.config_json.get("account_sid") or decrypt(row.encrypted_api_key))
        auth_token = str(row.config_json.get("auth_token") or decrypt(row.encrypted_api_secret or ""))
    except ValueError:
        logger.warning("Skipping unreadable Twilio provider credential row")
        return "", ""
    return account_sid, auth_token


@router.post("/twiml")
async def twiml_handler(request: Request, session: SessionDep) -> Response:
    """Return TwiML to connect the call to our WebSocket media stream."""
    form_data = await request.form()
    params = {k: str(v) for k, v in form_data.items()}
    _verify_twilio_webhook(request, params, session)

    call_sid = params.get("CallSid", "")
    if not call_sid:
        raise HTTPException(status_code=400, detail="Missing CallSid")
    account_sid = params.get("AccountSid", "")

    host = settings.SERVER_HOST
    ws_scheme = "wss" if request.url.scheme == "https" else "ws"
    token = _build_media_stream_token(call_sid, account_sid)
    query = urlencode(
        {
            MEDIA_CALL_QUERY_PARAM: call_sid,
            MEDIA_ACCOUNT_QUERY_PARAM: account_sid,
            MEDIA_TOKEN_QUERY_PARAM: token,
        }
    )
    stream_url = f"{ws_scheme}://{host}{settings.API_V1_STR}/voice/media-stream?{query}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url={quoteattr(stream_url)}>
            <Parameter name="call_sid" value={quoteattr(call_sid)} />
            <Parameter name="account_sid" value={quoteattr(account_sid)} />
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.websocket("/media-stream")
async def media_stream(websocket: WebSocket) -> None:
    """Handle Twilio Media Streams WebSocket for real-time audio."""
    media_token = websocket.query_params.get(MEDIA_TOKEN_QUERY_PARAM, "")
    expected_call_sid = websocket.query_params.get(MEDIA_CALL_QUERY_PARAM, "")
    expected_account_sid = websocket.query_params.get(MEDIA_ACCOUNT_QUERY_PARAM, "")
    if not expected_call_sid or not media_token or not _verify_media_stream_token(
        expected_call_sid,
        expected_account_sid,
        media_token,
    ):
        await websocket.close(code=1008)
        return

    await websocket.accept()

    conv_engine: ConversationEngine | None = None
    call_sid = ""
    stream_sid = ""
    stt_task: asyncio.Task | None = None
    connected_at = time.monotonic()
    save_results = False

    try:
        while True:
            remaining_call_seconds = MEDIA_STREAM_MAX_CALL_SECONDS - (time.monotonic() - connected_at)
            if remaining_call_seconds <= 0:
                logger.warning("Media stream max call timeout: call=%s", call_sid)
                save_results = False
                break

            try:
                raw_message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=min(MEDIA_STREAM_IDLE_TIMEOUT_SECONDS, remaining_call_seconds),
                )
            except TimeoutError:
                logger.warning("Media stream idle timeout: call=%s", call_sid)
                save_results = False
                break

            try:
                msg = json.loads(raw_message)
            except json.JSONDecodeError:
                logger.warning("Ignoring malformed media stream frame: call=%s", call_sid)
                await websocket.close(code=1003)
                save_results = False
                return

            event = msg.get("event")

            if event == "start":
                if conv_engine is not None:
                    logger.warning("Ignoring duplicate media stream start: call=%s", call_sid)
                    continue

                start_data = msg.get("start", {})
                call_sid = start_data.get("callSid", "")
                stream_sid = start_data.get("streamSid", "")
                account_sid = start_data.get("accountSid", "")
                custom_params = start_data.get("customParameters", {}) or {}
                if (
                    call_sid != expected_call_sid
                    or account_sid != expected_account_sid
                    or custom_params.get("call_sid") not in (None, "", expected_call_sid)
                    or custom_params.get("account_sid") not in (None, "", expected_account_sid)
                    or not stream_sid
                ):
                    logger.warning("Rejected unauthorized media stream start")
                    await websocket.close(code=1008)
                    save_results = False
                    return

                logger.info("Media stream started: call=%s stream=%s", call_sid, stream_sid)

                # Load script for this call
                conv_engine = await _load_engine_for_call(call_sid)
                if conv_engine is None:
                    await websocket.close(code=1008)
                    save_results = False
                    return

                save_results = True
                await conv_engine.start_stt()
                stt_task = asyncio.create_task(
                    _stt_receive_loop(websocket, stream_sid, conv_engine)
                )
                opening = await conv_engine.get_opening()
                await _stream_text_to_twilio(websocket, stream_sid, conv_engine, opening)

            elif event == "media":
                if conv_engine is None:
                    logger.warning("Rejected media frame before start")
                    await websocket.close(code=1008)
                    save_results = False
                    return
                payload = msg.get("media", {}).get("payload", "")
                try:
                    audio_bytes = base64.b64decode(payload, validate=True)
                except (binascii.Error, ValueError):
                    logger.warning("Invalid media payload: call=%s", call_sid)
                    await websocket.close(code=1003)
                    save_results = False
                    return
                await conv_engine.send_audio_to_stt(audio_bytes)

            elif event == "stop":
                logger.info("Media stream stopped: call=%s", call_sid)
                if conv_engine:
                    await conv_engine.close_stt()
                break

            elif event == "error":
                logger.warning("Media stream error event: call=%s", call_sid)
                save_results = False
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: call=%s", call_sid)
    except ProviderConfigurationError:
        logger.error("Voice provider configuration error: call=%s", call_sid)
        save_results = False
    except Exception:
        logger.exception("Media stream error: call=%s", call_sid)
        save_results = False
    finally:
        await _cancel_task(stt_task)
        if conv_engine:
            await _close_stt_safely(conv_engine)
            # Save conversation results in executor to avoid blocking
            if call_sid and save_results:
                import functools
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, functools.partial(_save_conversation_results, call_sid, conv_engine)
                )


def _build_media_stream_token(call_sid: str, account_sid: str) -> str:
    """Return a per-call HMAC token for Twilio Media Stream binding."""
    token_subject = f"{account_sid}:{call_sid}"
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        token_subject.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _verify_media_stream_token(call_sid: str, account_sid: str, token: str) -> bool:
    """Verify that a media stream token was minted for the Twilio call SID."""
    expected = _build_media_stream_token(call_sid, account_sid)
    return hmac.compare_digest(expected, token)


async def _cancel_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await task


async def _close_stt_safely(conv_engine: ConversationEngine) -> None:
    with suppress(asyncio.TimeoutError, Exception):
        await asyncio.wait_for(conv_engine.close_stt(), timeout=MEDIA_STREAM_CLOSE_TIMEOUT_SECONDS)


async def _load_engine_for_call(call_sid: str) -> ConversationEngine | None:
    """Load the voice script and contact info for a call."""
    with Session(engine) as session:
        call_session = session.exec(
            select(CallSession).where(CallSession.twilio_call_sid == call_sid)
        ).first()
        if not call_session:
            logger.warning("No CallSession for sid=%s", call_sid)
            return None
        if call_session.outcome == CallOutcome.voicemail:
            logger.info("Skipping media stream for voicemail call: sid=%s", call_sid)
            return None

        call_request = session.get(CallRequest, call_session.call_request_id)
        if not call_request:
            return None

        voice_script = session.get(VoiceScript, call_request.voice_script_id)
        if not voice_script:
            return None

        contact = session.get(Contact, call_request.contact_id)
        contact_name = contact.first_name or "there" if contact else "there"
        contact_company = contact.company or "" if contact else ""

    parsed = parse_script(voice_script.content)
    return ConversationEngine(
        script=parsed,
        contact_name=contact_name,
        contact_company=contact_company,
    )


async def _stt_receive_loop(
    websocket: WebSocket, stream_sid: str, conv_engine: ConversationEngine
) -> None:
    """Background task: receive STT transcripts and generate responses."""
    try:
        async for result in conv_engine.stt.receive_loop():
            if result.get("is_final") and result.get("transcript"):
                transcript = result["transcript"]
                logger.info("Received final user transcript: chars=%d", len(transcript))

                started_at = time.perf_counter()
                try:
                    response_text = await conv_engine.process_user_speech(transcript)
                    if response_text:
                        first_audio_sent = await _stream_text_to_twilio(
                            websocket, stream_sid, conv_engine, response_text
                        )
                        elapsed = time.perf_counter() - started_at
                        if first_audio_sent and elapsed > RESPONSE_LATENCY_BUDGET_SECONDS:
                            logger.warning("Voice response exceeded latency budget: %.0fms", elapsed * 1000)
                except Exception:
                    logger.exception("Voice response generation failed")
    except Exception:
        logger.exception("STT receive loop error")


async def _stream_text_to_twilio(
    websocket: WebSocket,
    stream_sid: str,
    conv_engine: ConversationEngine,
    text: str,
) -> bool:
    """Stream synthesized text to Twilio and return True once first audio is sent."""
    audio_stream = conv_engine.synthesize_response_stream(text)
    try:
        first_chunk = await asyncio.wait_for(
            audio_stream.__anext__(),
            timeout=TTS_FIRST_AUDIO_TIMEOUT_SECONDS,
        )
    except StopAsyncIteration:
        return False
    except TimeoutError:
        logger.warning("TTS first-audio timeout: stream=%s", stream_sid)
        with suppress(Exception):
            await audio_stream.aclose()
        return False

    await _send_audio_chunk_to_twilio(websocket, stream_sid, first_chunk)
    async for chunk in audio_stream:
        await _send_audio_chunk_to_twilio(websocket, stream_sid, chunk)
    return True


async def _send_audio_to_twilio(
    websocket: WebSocket, stream_sid: str, audio_bytes: bytes
) -> None:
    """Send audio back through Twilio Media Stream."""
    # Send in chunks matching Twilio's expected frame size
    chunk_size = 640  # 80ms of μ-law 8kHz audio
    for i in range(0, len(audio_bytes), chunk_size):
        chunk = audio_bytes[i : i + chunk_size]
        await _send_audio_chunk_to_twilio(websocket, stream_sid, chunk)


async def _send_audio_chunk_to_twilio(
    websocket: WebSocket, stream_sid: str, chunk: bytes
) -> None:
    if not chunk:
        return
    payload = base64.b64encode(chunk).decode("utf-8")
    msg = json.dumps({
        "event": "media",
        "streamSid": stream_sid,
        "media": {"payload": payload},
    })
    await websocket.send_text(msg)


def _save_conversation_results(call_sid: str, conv_engine: ConversationEngine) -> None:
    """Save conversation state to CallSession after call ends."""
    with Session(engine) as session:
        call_session = session.exec(
            select(CallSession).where(CallSession.twilio_call_sid == call_sid)
        ).first()
        if call_session:
            call_request = session.get(CallRequest, call_session.call_request_id)
            state = conv_engine.state
            call_session.transcript = "\n".join(
                f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}"
                for m in state.messages
            )
            call_session.unanswered_questions = (
                {"questions": state.unanswered_questions}
                if state.unanswered_questions
                else None
            )
            call_session.scheduling_interest = state.scheduling_interest
            session.add(call_session)
            session.commit()
            if call_request:
                invalidate_timeline_cache_from_url_sync(
                    settings.REDIS_URL,
                    call_request.contact_id,
                    call_request.campaign_id,
                )


@router.post("/status")
async def status_callback(request: Request, session: SessionDep) -> dict[str, str]:
    """Handle Twilio call status callbacks."""
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    _verify_twilio_webhook(request, params, session)

    call_sid = str(form.get("CallSid", ""))
    call_status = str(form.get("CallStatus", "")).lower()
    if not call_sid or not call_status:
        raise HTTPException(status_code=400, detail="Missing CallSid or CallStatus")

    call_session = session.exec(
        select(CallSession).where(CallSession.twilio_call_sid == call_sid)
    ).first()

    if not call_session:
        logger.warning("Status callback for unknown call_sid=%s", call_sid)
        return {"status": "ignored"}

    if not _should_apply_twilio_status(call_session.twilio_status, call_status):
        logger.info("Ignoring stale Twilio status: call=%s status=%s", call_sid, call_status)
        return {"status": "ignored"}

    duration = _parse_positive_int(str(form.get("CallDuration", "0")))
    account_sid = str(form.get("AccountSid", ""))
    answered_by = str(form.get("AnsweredBy", "")).lower()

    call_session.twilio_status = call_status
    call_session.twilio_account_sid = account_sid or call_session.twilio_account_sid
    call_session.twilio_status_updated_at = datetime.now(timezone.utc)
    call_session.duration_seconds = duration

    if _answered_by_voicemail(answered_by):
        call_session.outcome = CallOutcome.voicemail
    elif call_session.outcome != CallOutcome.voicemail:
        outcome = TWILIO_STATUS_MAP.get(call_status)
        if outcome:
            call_session.outcome = outcome

    call_request = session.get(CallRequest, call_session.call_request_id)
    if call_request:
        _apply_call_request_status(call_request, call_status, call_session.outcome)

    session.add(call_session)
    if call_request:
        session.add(call_request)
    session.commit()
    if call_request:
        await invalidate_timeline_cache(request, call_request.contact_id, call_request.campaign_id)

    return {"status": "ok"}


@router.post("/recording")
async def recording_callback(request: Request, session: SessionDep) -> dict[str, str]:
    """Handle Twilio recording callbacks."""
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    _verify_twilio_webhook(request, params, session)

    call_sid = str(form.get("CallSid", ""))
    recording_url = str(form.get("RecordingUrl", ""))

    if recording_url:
        call_session = session.exec(
            select(CallSession).where(CallSession.twilio_call_sid == call_sid)
        ).first()
        if call_session:
            call_request = session.get(CallRequest, call_session.call_request_id)
            call_session.twilio_account_sid = str(form.get("AccountSid", "")) or call_session.twilio_account_sid
            if not call_session.recording_url or call_session.recording_url == recording_url:
                call_session.recording_url = recording_url
            session.add(call_session)
            session.commit()
            if call_request:
                await invalidate_timeline_cache(
                    request,
                    call_request.contact_id,
                    call_request.campaign_id,
                )

    return {"status": "ok"}


def _parse_positive_int(value: str) -> int:
    try:
        parsed = int(value or "0")
    except ValueError:
        return 0
    return max(parsed, 0)


def _answered_by_voicemail(answered_by: str) -> bool:
    return answered_by.startswith("machine") or answered_by == "fax"


def _should_apply_twilio_status(current_status: str | None, incoming_status: str) -> bool:
    if not current_status or current_status == incoming_status:
        return True
    if current_status in TERMINAL_TWILIO_STATUSES:
        return False
    return TWILIO_STATUS_RANK.get(incoming_status, 0) >= TWILIO_STATUS_RANK.get(current_status, 0)


def _apply_call_request_status(
    call_request: CallRequest,
    call_status: str,
    outcome: CallOutcome | None,
) -> None:
    if outcome == CallOutcome.voicemail or call_status == "completed":
        call_request.status = CallRequestStatus.completed
    elif call_status in {"busy", "canceled", "failed", "no-answer"}:
        call_request.status = CallRequestStatus.failed
    elif call_status in ACTIVE_TWILIO_STATUSES:
        call_request.status = CallRequestStatus.in_progress
