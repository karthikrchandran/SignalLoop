"""Capability-aware provider registry.

Workers and route handlers used to hard-code a single concrete adapter
(SendGrid for email, Twilio for voice, Deepgram for STT/TTS, Groq for LLM).
This registry centralises selection so callers can simply ask::

    adapter = resolve_email_adapter(session, workspace_id)
    await adapter.send_email(...)

and the right concrete adapter is constructed using whatever
``WorkspaceProviderSelection`` / ``ProviderCredential`` rows exist for that
workspace.  If nothing is configured we fall back to the historical default
(SendGrid / Twilio / Deepgram / Groq) so single-tenant ``.env``-only
deployments keep working unchanged.

Notes
-----
* The registry is intentionally a single module instead of a class — there
  is no per-instance state worth keeping.
* New providers are added by:
    1. Extending the ``NotificationProvider`` enum in ``domain_models``.
    2. Writing an adapter that subclasses the relevant capability ABC.
    3. Adding the (provider, capability) → factory mapping in
       :data:`_PROVIDER_MAP` below.
* Adapters must accept all their construction params as keyword arguments
  with sensible names so the resolver can splat ``creds`` straight in
  (``Adapter(**creds_subset)``).
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.domain.providers.credential_resolver import (
    get_workspace_provider_selection,
    resolve_active_provider,
    resolve_provider_credentials,
)
from app.domain_models import NotificationProvider, ProviderCapability
from app.infrastructure.providers.base import (
    CapabilityAdapter,
    EmailAdapter,
    LlmAdapter,
    SmsAdapter,
    SttAdapter,
    TtsAdapter,
    VoiceAdapter,
)
from app.infrastructure.providers.deepgram_stt import DeepgramSTTAdapter
from app.infrastructure.providers.deepgram_tts import DeepgramTTSAdapter
from app.infrastructure.providers.groq_llm import GroqLLMAdapter
from app.infrastructure.providers.ollama_llm import OllamaLLMAdapter
from app.infrastructure.providers.openai_llm import OpenAILLMAdapter
from app.infrastructure.providers.sendgrid import SendGridAdapter
from app.infrastructure.providers.smtp_email import SmtpEmailAdapter
from app.infrastructure.providers.twilio_sms import TwilioSmsAdapter
from app.infrastructure.providers.twilio_voice import TwilioVoiceAdapter
from app.infrastructure.providers.vapi_voice import VapiVoiceAdapter
from app.infrastructure.providers.whisper_stt import FasterWhisperLocalAdapter

logger = logging.getLogger(__name__)


# A "factory" takes a creds dict and returns a configured adapter instance.
ProviderFactory = Callable[[dict[str, Any]], CapabilityAdapter]


def _sendgrid_factory(creds: dict[str, Any]) -> EmailAdapter:
    return SendGridAdapter(
        api_key=creds.get("api_key"),
        from_email=creds.get("from_email"),
    )


def _smtp_factory(creds: dict[str, Any]) -> EmailAdapter:
    return SmtpEmailAdapter(
        host=creds.get("host") or "",
        port=creds.get("port") or None,
        username=creds.get("username") or None,
        password=creds.get("password") or None,
        from_email=creds.get("from_email") or "",
        from_name=creds.get("from_name") or None,
        use_tls=bool(creds.get("use_tls", False)),
        use_starttls=bool(creds.get("use_starttls", True)),
    )


def _twilio_voice_factory(creds: dict[str, Any]) -> VoiceAdapter:
    return TwilioVoiceAdapter(
        account_sid=creds.get("account_sid") or creds.get("api_key"),
        auth_token=creds.get("auth_token") or creds.get("api_secret"),
        from_number=creds.get("phone_number"),
    )


def _vapi_voice_factory(creds: dict[str, Any]) -> VoiceAdapter:
    return VapiVoiceAdapter(
        api_key=creds.get("api_key"),
        phone_number_id=creds.get("phone_number_id"),
        assistant_id=creds.get("assistant_id"),
        base_url=creds.get("base_url"),
        call_endpoint=creds.get("call_endpoint"),
    )


def _twilio_sms_factory(creds: dict[str, Any]) -> SmsAdapter:
    return TwilioSmsAdapter(
        account_sid=creds.get("account_sid") or creds.get("api_key"),
        auth_token=creds.get("auth_token") or creds.get("api_secret"),
        from_number=creds.get("phone_number"),
    )


def _deepgram_stt_factory(creds: dict[str, Any]) -> SttAdapter:
    return DeepgramSTTAdapter(api_key=creds.get("api_key"))


def _deepgram_tts_factory(creds: dict[str, Any]) -> TtsAdapter:
    return DeepgramTTSAdapter(api_key=creds.get("api_key"))


def _faster_whisper_factory(creds: dict[str, Any]) -> SttAdapter:
    return FasterWhisperLocalAdapter(
        base_url=creds.get("base_url") or None,
        model=creds.get("model") or None,
    )


def _groq_factory(creds: dict[str, Any]) -> LlmAdapter:
    return GroqLLMAdapter(api_key=creds.get("api_key"))


def _openai_factory(creds: dict[str, Any]) -> LlmAdapter:
    return OpenAILLMAdapter(
        api_key=creds.get("api_key") or "",
        base_url=creds.get("base_url") or None,
        model=creds.get("model") or None,
    )


def _ollama_factory(creds: dict[str, Any]) -> LlmAdapter:
    return OllamaLLMAdapter(
        base_url=creds.get("base_url") or None,
        model=creds.get("model") or None,
    )


# (provider, capability) → factory
_PROVIDER_MAP: dict[
    tuple[NotificationProvider, ProviderCapability], ProviderFactory
] = {
    # Email
    (NotificationProvider.sendgrid, ProviderCapability.email): _sendgrid_factory,
    (NotificationProvider.smtp, ProviderCapability.email): _smtp_factory,
    # Voice / SMS
    (NotificationProvider.twilio, ProviderCapability.sms): _twilio_sms_factory,
    (NotificationProvider.twilio, ProviderCapability.voice): _twilio_voice_factory,
    (NotificationProvider.vapi, ProviderCapability.voice): _vapi_voice_factory,
    # STT / TTS
    (NotificationProvider.deepgram, ProviderCapability.stt): _deepgram_stt_factory,
    (
        NotificationProvider.faster_whisper_local,
        ProviderCapability.stt,
    ): _faster_whisper_factory,
    (NotificationProvider.deepgram, ProviderCapability.tts): _deepgram_tts_factory,
    # LLM
    (NotificationProvider.groq, ProviderCapability.llm): _groq_factory,
    (NotificationProvider.openai, ProviderCapability.llm): _openai_factory,
    (NotificationProvider.openrouter, ProviderCapability.llm): _openai_factory,
    (NotificationProvider.together, ProviderCapability.llm): _openai_factory,
    (NotificationProvider.ollama_local, ProviderCapability.llm): _ollama_factory,
}


# Capability → channel name to pass to resolve_provider_credentials.
_CAPABILITY_CHANNEL: dict[ProviderCapability, str] = {
    ProviderCapability.email: "email",
    ProviderCapability.sms: "sms",
    ProviderCapability.voice: "voice",
    ProviderCapability.stt: "voice",
    ProviderCapability.tts: "voice",
    ProviderCapability.llm: "voice",
}


class ProviderResolutionError(RuntimeError):
    """Raised when no factory is registered and no default is supplied."""


def build_adapter_from_credential(
    session: Session,
    *,
    workspace_id: str,
    provider: NotificationProvider,
    capability: ProviderCapability,
) -> CapabilityAdapter:
    """Construct an adapter for the given (provider, capability) using stored creds.

    Bypasses the workspace's active selection — useful for diagnostics (e.g.
    "test this credential") regardless of which provider is currently selected.
    """
    factory = _PROVIDER_MAP.get((provider, capability))
    if factory is None:
        raise ProviderResolutionError(
            f"No adapter factory for provider={provider.value} "
            f"capability={capability.value}"
        )
    creds = resolve_provider_credentials(
        session,
        workspace_id=workspace_id,
        provider=provider,
        channel=_CAPABILITY_CHANNEL[capability],
    )
    return factory(creds)


def get_adapter(
    session: Session,
    *,
    workspace_id: str,
    capability: ProviderCapability,
    default_factory: Callable[[], CapabilityAdapter] | None = None,
) -> CapabilityAdapter:
    """Return a configured adapter for *capability* in *workspace_id*.

    Resolution rules:
      1. If the workspace has NOT opted-in (no ``WorkspaceProviderSelection``
         row) AND a *default_factory* is supplied, return ``default_factory()``
         immediately.  This preserves the legacy single-tenant behaviour and
         keeps existing ``patch.object`` test hooks working.
      2. Otherwise resolve the active provider (explicit selection or built-in
         default), look up its factory in :data:`_PROVIDER_MAP`, fetch
         credentials, and instantiate the adapter.
      3. On any failure during steps 2, fall back to *default_factory* if
         supplied, else re-raise.
    """
    explicit = get_workspace_provider_selection(session, workspace_id, capability)
    if explicit is None and default_factory is not None:
        return default_factory()

    try:
        provider = explicit or resolve_active_provider(
            session, workspace_id, capability
        )
        factory = _PROVIDER_MAP.get((provider, capability))
        if factory is None:
            raise ProviderResolutionError(
                f"No adapter factory for provider={provider.value} "
                f"capability={capability.value}"
            )
        creds = resolve_provider_credentials(
            session,
            workspace_id=workspace_id,
            provider=provider,
            channel=_CAPABILITY_CHANNEL[capability],
        )
        return factory(creds)
    except Exception:
        if default_factory is None:
            raise
        logger.exception(
            "Provider resolution failed for workspace=%s capability=%s; using default",
            workspace_id,
            capability.value,
        )
        return default_factory()


# Convenience helpers — one per capability for readability at call sites.

def resolve_email_adapter(
    session: Session,
    workspace_id: str,
    *,
    default_factory: Callable[[], EmailAdapter] | None = None,
) -> EmailAdapter:
    return get_adapter(  # type: ignore[return-value]
        session,
        workspace_id=workspace_id,
        capability=ProviderCapability.email,
        default_factory=default_factory,
    )


def resolve_sms_adapter(
    session: Session,
    workspace_id: str,
    *,
    default_factory: Callable[[], SmsAdapter] | None = None,
) -> SmsAdapter:
    return get_adapter(  # type: ignore[return-value]
        session,
        workspace_id=workspace_id,
        capability=ProviderCapability.sms,
        default_factory=default_factory,
    )


def resolve_voice_adapter(
    session: Session,
    workspace_id: str,
    *,
    default_factory: Callable[[], VoiceAdapter] | None = None,
) -> VoiceAdapter:
    return get_adapter(  # type: ignore[return-value]
        session,
        workspace_id=workspace_id,
        capability=ProviderCapability.voice,
        default_factory=default_factory,
    )


def resolve_stt_adapter(
    session: Session,
    workspace_id: str,
    *,
    default_factory: Callable[[], SttAdapter] | None = None,
) -> SttAdapter:
    return get_adapter(  # type: ignore[return-value]
        session,
        workspace_id=workspace_id,
        capability=ProviderCapability.stt,
        default_factory=default_factory,
    )


def resolve_tts_adapter(
    session: Session,
    workspace_id: str,
    *,
    default_factory: Callable[[], TtsAdapter] | None = None,
) -> TtsAdapter:
    return get_adapter(  # type: ignore[return-value]
        session,
        workspace_id=workspace_id,
        capability=ProviderCapability.tts,
        default_factory=default_factory,
    )


def resolve_llm_adapter(
    session: Session,
    workspace_id: str,
    *,
    default_factory: Callable[[], LlmAdapter] | None = None,
) -> LlmAdapter:
    return get_adapter(  # type: ignore[return-value]
        session,
        workspace_id=workspace_id,
        capability=ProviderCapability.llm,
        default_factory=default_factory,
    )


# ---------------------------------------------------------------------------
# Catalog (used by the GET /provider-options route)
# ---------------------------------------------------------------------------

PROVIDER_CATALOG: dict[str, list[dict[str, Any]]] = {
    ProviderCapability.email.value: [
        {
            "provider": NotificationProvider.sendgrid.value,
            "label": "SendGrid",
            "requires_creds": True,
            "free_tier": "100 emails/day",
            "local": False,
        },
        {
            "provider": NotificationProvider.smtp.value,
            "label": "Generic SMTP / Mailpit (local dev, Gmail, SES SMTP, ...)",
            "requires_creds": False,
            "free_tier": "Free (local Mailpit or bring-your-own relay)",
            "local": True,
        },
    ],
    ProviderCapability.sms.value: [
        {
            "provider": NotificationProvider.twilio.value,
            "label": "Twilio SMS",
            "requires_creds": True,
            "free_tier": "Trial credit",
            "local": False,
        },
    ],
    ProviderCapability.voice.value: [
        {
            "provider": NotificationProvider.twilio.value,
            "label": "Twilio Voice",
            "requires_creds": True,
            "free_tier": "Trial credit",
            "local": False,
        },
        {
            "provider": NotificationProvider.vapi.value,
            "label": "Vapi AI Voice",
            "requires_creds": True,
            "free_tier": "Starter credits / free testing numbers",
            "local": False,
        },
    ],
    ProviderCapability.stt.value: [
        {
            "provider": NotificationProvider.deepgram.value,
            "label": "Deepgram Nova-2",
            "requires_creds": True,
            "free_tier": "$200 credit",
            "local": False,
        },
        {
            "provider": NotificationProvider.faster_whisper_local.value,
            "label": "Faster Whisper Local (zero cost, CPU/GPU)",
            "requires_creds": False,
            "free_tier": "Free (your hardware)",
            "local": True,
        },
    ],
    ProviderCapability.tts.value: [
        {
            "provider": NotificationProvider.deepgram.value,
            "label": "Deepgram Aura",
            "requires_creds": True,
            "free_tier": "$200 credit",
            "local": False,
        },
    ],
    ProviderCapability.llm.value: [
        {
            "provider": NotificationProvider.groq.value,
            "label": "Groq (Llama 3.1)",
            "requires_creds": True,
            "free_tier": "Generous free tier",
            "local": False,
        },
        {
            "provider": NotificationProvider.openai.value,
            "label": "OpenAI (gpt-4o-mini etc.)",
            "requires_creds": True,
            "free_tier": "Pay-as-you-go",
            "local": False,
        },
        {
            "provider": NotificationProvider.openrouter.value,
            "label": "OpenRouter (multi-model gateway)",
            "requires_creds": True,
            "free_tier": "Pay-as-you-go",
            "local": False,
        },
        {
            "provider": NotificationProvider.together.value,
            "label": "Together AI",
            "requires_creds": True,
            "free_tier": "Pay-as-you-go",
            "local": False,
        },
        {
            "provider": NotificationProvider.ollama_local.value,
            "label": "Ollama (self-hosted - zero cost)",
            "requires_creds": False,
            "free_tier": "Free (your hardware)",
            "local": True,
        },
    ],
}
