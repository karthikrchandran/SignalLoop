"""Provider webhook routes for ChatBot Hub channels."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import SessionDep
from app.core.encryption import decrypt
from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.chatbot.models import ChatbotChannelConfig
from app.domain.chatbot.webhook_ingestion import enqueue_inbound_message
from app.domain_models import ProviderCredential
from app.infrastructure.providers.chat.registry import build_chat_adapter

router = APIRouter(prefix="/webhooks", tags=["chatbot-webhooks"])


def _redis_client(request: Request):
    manager = getattr(request.app.state, "redis_manager", None)
    redis = getattr(manager, "client", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis is not available")
    return redis


def _headers(request: Request) -> dict[str, str]:
    return {key.lower(): value for key, value in request.headers.items()}


def _load_channel(session: SessionDep, channel_id: uuid.UUID) -> ChatbotChannelConfig:
    channel = session.get(ChatbotChannelConfig, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


def _credential(session: SessionDep, channel: ChatbotChannelConfig) -> ProviderCredential | None:
    if not channel.credential_id:
        return None
    return session.get(ProviderCredential, channel.credential_id)


def _webhook_secret(credential: ProviderCredential | None) -> str:
    if not credential:
        return ""
    if credential.encrypted_api_secret:
        return decrypt(credential.encrypted_api_secret)
    secret = credential.config_json.get("webhook_secret")
    return str(secret or "")


@router.get("/{channel_id}")
def verify_channel_webhook(
    channel_id: uuid.UUID,
    request: Request,
    session: SessionDep,
) -> Response:
    """Handle provider verification challenges."""
    channel = _load_channel(session, channel_id)
    adapter = build_chat_adapter(channel.channel_type)
    credential = _credential(session, channel)
    verify_token = str((credential.config_json if credential else {}).get("verify_token") or "")
    challenge = adapter.verify_challenge(dict(request.query_params), verify_token)
    if challenge is None:
        append_audit_event_to_session(
            session,
            event_name="chatbot_webhook_challenge_failed",
            workspace_id=channel.workspace_id,
            actor_role="system",
            resource_type="chatbot_channel",
            resource_id=str(channel.id),
            payload={"channel_type": channel.channel_type.value},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid challenge")
    return Response(content=challenge, media_type="text/plain")


@router.post("/{channel_id}")
async def ingest_channel_webhook(
    channel_id: uuid.UUID,
    request: Request,
    session: SessionDep,
) -> dict[str, object]:
    """Verify, normalize, deduplicate, and enqueue inbound chat messages."""
    channel = _load_channel(session, channel_id)
    adapter = build_chat_adapter(channel.channel_type)
    credential = _credential(session, channel)
    body = await request.body()
    secret = _webhook_secret(credential)

    if not adapter.verify_webhook(body, _headers(request), secret):
        append_audit_event_to_session(
            session,
            event_name="chatbot_webhook_signature_invalid",
            workspace_id=channel.workspace_id,
            actor_role="system",
            resource_type="chatbot_channel",
            resource_id=str(channel.id),
            payload={"channel_type": channel.channel_type.value},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    if not channel.is_active:
        return {"status": "inactive", "queued": 0, "duplicates": 0}

    try:
        payload = json.loads(body.decode() or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    queued = 0
    duplicates = 0
    redis = _redis_client(request)
    for message in adapter.parse_event(payload):
        result = await enqueue_inbound_message(
            redis,
            workspace_id=channel.workspace_id,
            channel_type=channel.channel_type,
            provider_message_id=message.provider_message_id,
            payload={
                "channel_id": str(channel.id),
                "visitor_id": message.visitor_id,
                "text": message.text,
                "is_text": message.is_text,
                "is_opt_out": message.is_opt_out,
                "raw_payload": message.raw_payload,
            },
        )
        if result == "duplicate":
            duplicates += 1
        else:
            queued += 1

    append_audit_event_to_session(
        session,
        event_name="chatbot_webhook_ingested",
        workspace_id=channel.workspace_id,
        actor_role="system",
        resource_type="chatbot_channel",
        resource_id=str(channel.id),
        payload={"queued": queued, "duplicates": duplicates},
    )
    session.commit()
    return {"status": "ok", "queued": queued, "duplicates": duplicates}
