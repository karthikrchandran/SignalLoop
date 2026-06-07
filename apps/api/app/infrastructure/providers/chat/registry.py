"""Registry for ChatBot Hub channel adapters."""

from __future__ import annotations

from app.domain.chatbot.models import ChatbotChannelType
from app.domain_models import NotificationProvider
from app.infrastructure.providers.chat.base import ChatChannelAdapter
from app.infrastructure.providers.chat.facebook_messenger import (
    FacebookMessengerAdapter,
)
from app.infrastructure.providers.chat.telegram_bot import TelegramBotAdapter
from app.infrastructure.providers.chat.whatsapp_cloud import WhatsAppCloudAdapter

ADAPTERS: dict[ChatbotChannelType, type[ChatChannelAdapter]] = {
    ChatbotChannelType.facebook_messenger: FacebookMessengerAdapter,
    ChatbotChannelType.whatsapp_business: WhatsAppCloudAdapter,
    ChatbotChannelType.telegram: TelegramBotAdapter,
}

CHANNEL_PROVIDER_MAP: dict[ChatbotChannelType, NotificationProvider] = {
    ChatbotChannelType.facebook_messenger: NotificationProvider.facebook_messenger,
    ChatbotChannelType.whatsapp_business: NotificationProvider.whatsapp_cloud,
    ChatbotChannelType.telegram: NotificationProvider.telegram_bot,
    ChatbotChannelType.linkedin_redirect: NotificationProvider.linkedin_redirect,
}


def build_chat_adapter(channel_type: ChatbotChannelType) -> ChatChannelAdapter:
    """Build an adapter for the requested channel."""
    adapter_cls = ADAPTERS.get(channel_type)
    if adapter_cls is None:
        raise KeyError(f"No chat adapter registered for {channel_type.value}")
    return adapter_cls()


def provider_for_channel(channel_type: ChatbotChannelType) -> NotificationProvider:
    """Return the ProviderCredential provider value for a chat channel."""
    return CHANNEL_PROVIDER_MAP[channel_type]
