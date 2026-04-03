"""Voice call endpoints: TwiML, WebSocket media stream, status/recording callbacks."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.db import engine
from app.domain.voice.conversation_engine import ConversationEngine
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
    VoiceScript,
)
from app.domain.voice.script_parser import parse_script
from app.infrastructure.providers.twilio_voice import TwilioVoiceAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

# Map Twilio call statuses to our outcomes
TWILIO_STATUS_MAP = {
    "completed": CallOutcome.answered,
    "busy": CallOutcome.busy,
    "no-answer": CallOutcome.no_answer,
    "failed": CallOutcome.failed,
    "canceled": CallOutcome.failed,
}


@router.post("/twiml")
async def twiml_handler(request: Request) -> Response:
    """Return TwiML to connect the call to our WebSocket media stream."""
    # Verify Twilio signature
    form_data = await request.form()
    params = {k: str(v) for k, v in form_data.items()}
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not TwilioVoiceAdapter.verify_request_signature(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    host = settings.SERVER_HOST
    ws_scheme = "wss" if request.url.scheme == "https" else "ws"
    stream_url = f"{ws_scheme}://{host}{settings.API_V1_STR}/voice/media-stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}" />
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.websocket("/media-stream")
async def media_stream(websocket: WebSocket) -> None:
    """Handle Twilio Media Streams WebSocket for real-time audio."""
    await websocket.accept()

    conv_engine: ConversationEngine | None = None
    call_sid = ""
    stream_sid = ""
    stt_task: asyncio.Task | None = None

    try:
        async for raw_message in websocket.iter_text():
            msg = json.loads(raw_message)
            event = msg.get("event")

            if event == "start":
                start_data = msg.get("start", {})
                call_sid = start_data.get("callSid", "")
                stream_sid = start_data.get("streamSid", "")
                logger.info("Media stream started: call=%s stream=%s", call_sid, stream_sid)

                # Load script for this call
                conv_engine = await _load_engine_for_call(call_sid)
                if conv_engine:
                    await conv_engine.start_stt()
                    # Send opening pitch
                    opening = await conv_engine.get_opening()
                    audio = await conv_engine.synthesize_response(opening)
                    if audio:
                        await _send_audio_to_twilio(websocket, stream_sid, audio)
                    # Start STT receive loop in background
                    stt_task = asyncio.create_task(
                        _stt_receive_loop(websocket, stream_sid, conv_engine)
                    )

            elif event == "media":
                if conv_engine:
                    payload = msg.get("media", {}).get("payload", "")
                    audio_bytes = base64.b64decode(payload)
                    await conv_engine.send_audio_to_stt(audio_bytes)

            elif event == "stop":
                logger.info("Media stream stopped: call=%s", call_sid)
                if conv_engine:
                    await conv_engine.close_stt()
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: call=%s", call_sid)
    except Exception:
        logger.exception("Media stream error: call=%s", call_sid)
    finally:
        if stt_task and not stt_task.done():
            stt_task.cancel()
        if conv_engine:
            await conv_engine.close_stt()
            # Save conversation results in executor to avoid blocking
            import functools
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, functools.partial(_save_conversation_results, call_sid, conv_engine)
            )


async def _load_engine_for_call(call_sid: str) -> ConversationEngine | None:
    """Load the voice script and contact info for a call."""
    with Session(engine) as session:
        call_session = session.exec(
            select(CallSession).where(CallSession.twilio_call_sid == call_sid)
        ).first()
        if not call_session:
            logger.warning("No CallSession for sid=%s", call_sid)
            return None

        call_request = session.get(CallRequest, call_session.call_request_id)
        if not call_request:
            return None

        voice_script = session.get(VoiceScript, call_request.voice_script_id)
        if not voice_script:
            return None

        from app.domain_models import Contact
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
                logger.info("User said: %s", transcript)

                response_text = await conv_engine.process_user_speech(transcript)
                if response_text:
                    audio = await conv_engine.synthesize_response(response_text)
                    if audio:
                        await _send_audio_to_twilio(websocket, stream_sid, audio)
    except Exception:
        logger.exception("STT receive loop error")


async def _send_audio_to_twilio(
    websocket: WebSocket, stream_sid: str, audio_bytes: bytes
) -> None:
    """Send audio back through Twilio Media Stream."""
    # Send in chunks matching Twilio's expected frame size
    chunk_size = 640  # 80ms of μ-law 8kHz audio
    for i in range(0, len(audio_bytes), chunk_size):
        chunk = audio_bytes[i : i + chunk_size]
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


@router.post("/status")
async def status_callback(request: Request) -> dict[str, str]:
    """Handle Twilio call status callbacks."""
    form = await request.form()
    # Verify Twilio signature
    params = {k: str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not TwilioVoiceAdapter.verify_request_signature(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    call_sid = str(form.get("CallSid", ""))
    call_status = str(form.get("CallStatus", ""))
    duration = int(form.get("CallDuration", 0) or 0)

    with Session(engine) as session:
        call_session = session.exec(
            select(CallSession).where(CallSession.twilio_call_sid == call_sid)
        ).first()

        if not call_session:
            logger.warning("Status callback for unknown call_sid=%s", call_sid)
            return {"status": "ignored"}

        call_session.duration_seconds = duration

        outcome = TWILIO_STATUS_MAP.get(call_status)
        if outcome:
            call_session.outcome = outcome

        # Update the parent CallRequest status
        call_request = session.get(CallRequest, call_session.call_request_id)
        if call_request:
            if call_status == "completed":
                call_request.status = CallRequestStatus.completed
            elif call_status in ("busy", "no-answer", "failed", "canceled"):
                call_request.status = CallRequestStatus.failed

        session.add(call_session)
        if call_request:
            session.add(call_request)
        session.commit()

    return {"status": "ok"}


@router.post("/recording")
async def recording_callback(request: Request) -> dict[str, str]:
    """Handle Twilio recording callbacks."""
    form = await request.form()
    # Verify Twilio signature
    params = {k: str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not TwilioVoiceAdapter.verify_request_signature(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    call_sid = str(form.get("CallSid", ""))
    recording_url = str(form.get("RecordingUrl", ""))

    if recording_url:
        with Session(engine) as session:
            call_session = session.exec(
                select(CallSession).where(CallSession.twilio_call_sid == call_sid)
            ).first()
            if call_session:
                call_session.recording_url = recording_url
                session.add(call_session)
                session.commit()

    return {"status": "ok"}
