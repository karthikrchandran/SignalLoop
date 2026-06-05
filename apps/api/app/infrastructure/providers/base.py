"""Abstract base classes for capability-specific provider adapters.

Historically every provider implemented one monolithic
``NotificationProviderAdapter`` that exposed ``send_email``, ``send_sms``,
``make_call`` and ``normalize_webhook_event``.  That worked while we shipped
only SendGrid and Twilio, but it became awkward as we added providers that
own a single capability (Deepgram for STT/TTS, Groq for LLM, …).

This module now defines one ABC per capability so adapters only declare the
methods they actually implement.  ``NotificationProviderAdapter`` is kept as
a backwards-compatible composite for the legacy email-or-voice adapters
(SendGrid, Twilio) that already subclass it.

New adapters should subclass the most specific capability ABC
(``EmailAdapter``, ``SmsAdapter``, ``VoiceAdapter``, ``SttAdapter``,
``TtsAdapter`` or ``LlmAdapter``) — never ``NotificationProviderAdapter``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any


# ---------------------------------------------------------------------------
# Capability ABCs
# ---------------------------------------------------------------------------


class EmailAdapter(ABC):
    """Email-sending capability."""

    @abstractmethod
    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a transactional email. Returns the provider's raw response.

        ``kwargs`` is used for provider-specific extras such as
        ``idempotency_key``, ``reply_to`` or ``custom_args``.  Adapters that
        do not support a given extra should silently ignore it.
        """

    async def normalize_webhook_event(
        self, raw_payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalise a provider webhook payload into a canonical event dict.

        Optional — providers that do not push webhooks may leave this as the
        default no-op implementation.
        """
        return {}


class SmsAdapter(ABC):
    """SMS-sending capability."""

    @abstractmethod
    async def send_sms(self, *, to: str, message: str, **kwargs: Any) -> dict[str, Any]:
        """Send an SMS message. Returns the provider's raw response."""


class VoiceAdapter(ABC):
    """Outbound voice-call capability."""

    @abstractmethod
    async def initiate_call(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Initiate an outbound voice call. Returns the provider's raw response."""


class SttAdapter(ABC):
    """Real-time speech-to-text capability."""

    @abstractmethod
    async def connect(self) -> None:
        """Open the upstream streaming-STT session."""

    @abstractmethod
    async def send_audio(self, audio_bytes: bytes) -> None:
        """Push a chunk of caller audio upstream."""

    @abstractmethod
    def receive_loop(self) -> AsyncGenerator[dict[str, Any], None]:
        """Async generator yielding normalised transcript events."""

    @abstractmethod
    async def close(self) -> None:
        """Tear the upstream session down."""


class TtsAdapter(ABC):
    """Text-to-speech capability."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Render *text* into a single audio blob."""

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Yield audio chunks as they are produced.

        Default implementation falls back to a single ``synthesize`` call.
        """
        yield await self.synthesize(text)


class LlmAdapter(ABC):
    """Chat-completion LLM capability."""

    @abstractmethod
    async def chat_completion(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.4,
        **kwargs: Any,
    ) -> str:
        """Return the assistant text reply for *messages*."""


# ---------------------------------------------------------------------------
# Back-compat composite (SendGrid and Twilio still subclass this)
# ---------------------------------------------------------------------------


class NotificationProviderAdapter(EmailAdapter, SmsAdapter, VoiceAdapter):
    """Legacy composite ABC kept for backwards compatibility.

    New adapters MUST NOT subclass this — pick the capability ABC instead.
    """

    @abstractmethod
    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a transactional email."""

    @abstractmethod
    async def send_sms(self, *, to: str, message: str, **kwargs: Any) -> dict[str, Any]:
        """Send an SMS message."""

    async def initiate_call(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Initiate an outbound voice call.

        Default raises ``NotImplementedError`` so legacy email-only adapters
        that subclass this composite without overriding voice continue to
        behave the same way they did before.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support voice")

    @abstractmethod
    async def normalize_webhook_event(
        self, raw_payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalise a provider webhook payload into a canonical event dict.

        The canonical shape must include at least:
          • ``event_type``  – e.g. ``"delivered"``, ``"bounce"``, ``"opened"``
          • ``provider_event_id`` – unique ID from the provider
          • ``contact_identifier`` – email or phone of the recipient
          • ``occurred_at`` – ISO-8601 UTC timestamp
        """

    async def make_call(self, *, to: str, script: str) -> dict[str, Any]:
        """Legacy alias retained for the original ABC signature.

        Implementations may override either ``make_call`` or ``initiate_call``.
        The default delegates to ``initiate_call``.
        """
        return await self.initiate_call(to=to, script=script)


# Capability adapter union type (informative — used by registry helpers).
CapabilityAdapter = (
    EmailAdapter
    | SmsAdapter
    | VoiceAdapter
    | SttAdapter
    | TtsAdapter
    | LlmAdapter
)
