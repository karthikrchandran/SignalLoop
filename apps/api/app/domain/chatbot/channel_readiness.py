"""Readiness helpers for ChatBot Hub channel connections."""

from __future__ import annotations

from app.domain.chatbot.models import ChatbotChannelConfig, ChatbotChannelStatus, ChatbotChannelType
from app.domain.chatbot.schemas import ChatbotChannelReadinessPublic

REQUIRED_PROVIDER_FIELDS: dict[ChatbotChannelType, list[str]] = {
    ChatbotChannelType.facebook_messenger: ["page_id"],
    ChatbotChannelType.whatsapp_business: ["phone_number_id"],
    ChatbotChannelType.telegram: ["bot_username"],
    ChatbotChannelType.linkedin_redirect: ["redirect_url"],
}

VERIFY_TOKEN_CHANNELS = {
    ChatbotChannelType.facebook_messenger,
    ChatbotChannelType.whatsapp_business,
}


def webhook_url_path(channel_id: object) -> str:
    """Return the stable local API path providers should call for this channel."""
    return f"/api/v1/chatbot/webhooks/{channel_id}"


def build_channel_readiness(channel: ChatbotChannelConfig) -> ChatbotChannelReadinessPublic:
    """Build a real-connect checklist without exposing credential material."""
    config = channel.config_json or {}
    missing: list[str] = []

    if channel.credential_id is None:
        missing.append("provider credential")

    for field_name in REQUIRED_PROVIDER_FIELDS.get(channel.channel_type, []):
        if not str(config.get(field_name) or "").strip():
            missing.append(field_name)

    if not bool(config.get("webhook_secret_present") or channel.webhook_secret_hash):
        missing.append("webhook secret")

    if channel.channel_type in VERIFY_TOKEN_CHANNELS and not str(config.get("verify_token") or "").strip():
        missing.append("verify_token")

    if not channel.is_active:
        missing.append("activation")

    if channel.status == ChatbotChannelStatus.error:
        status = "error"
    elif channel.credential_id is None:
        status = "needs_credentials"
    elif "webhook secret" in missing or "verify_token" in missing:
        status = "needs_webhook"
    elif any(item not in {"activation"} for item in missing):
        status = "needs_provider_config"
    elif "activation" in missing:
        status = "needs_activation"
    else:
        status = "ready"

    return ChatbotChannelReadinessPublic(
        ready=status == "ready",
        status=status,
        missing=missing,
        webhook_url_path=webhook_url_path(channel.id),
    )
