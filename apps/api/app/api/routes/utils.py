"""FastAPI router: ``utils`` endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import anyio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic.networks import EmailStr
from sqlmodel import select

from app.api.deps import SessionDep, get_current_active_superuser, require_admin
from app.api.request_context import WorkspaceIdDep
from app.core.config import settings
from app.core.db import engine
from app.domain.providers.credential_resolver import (
    resolve_active_provider,
    resolve_provider_credentials,
)
from app.domain.runtime_settings import (
    ResolvedRuntimeValue,
    resolve_workspace_runtime_config,
)
from app.domain_models import (
    HealthStatus,
    NotificationProvider,
    ProviderCapability,
    ProviderCredential,
    WorkerHeartbeat,
)
from app.infrastructure.providers.registry import PROVIDER_CATALOG
from app.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class SetupIntegrationPublic(BaseModel):
    key: str
    label: str
    configured: bool
    source: str
    editable: bool
    has_secret: bool = False
    config: dict[str, str] = Field(default_factory=dict)
    note: str | None = None
    capability: ProviderCapability | None = None
    provider: NotificationProvider | None = None
    provider_label: str | None = None
    requires_creds: bool | None = None
    local: bool | None = None


class SetupWorkerReadinessPublic(BaseModel):
    key: str
    label: str
    ready: bool
    running: bool
    status: str
    last_seen_at: datetime | None = None
    last_error_message: str | None = None
    missing: list[str] = Field(default_factory=list)


class SetupCallbacksPublic(BaseModel):
    server_host: str
    public_base_url: str
    public_host: bool
    sendgrid_webhook_url: str
    twilio_twiml_url: str
    twilio_status_url: str
    twilio_recording_url: str
    twilio_media_stream_url: str


class SetupOverviewPublic(BaseModel):
    workspace_id: str
    health: HealthStatus
    integrations: list[SetupIntegrationPublic]
    worker_readiness: list[SetupWorkerReadinessPublic]
    callbacks: SetupCallbacksPublic


def _check_postgres_sync() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
        return True
    except Exception:
        return False


def _is_public_host(server_host: str) -> bool:
    host = server_host.strip().rstrip("/")
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0]
    host = host.split(":", 1)[0].strip("[]").lower()
    return host not in _LOCAL_HOSTS and not host.endswith(".local")


def _public_base_url(server_host: str) -> str:
    normalized = server_host.strip().rstrip("/")
    if normalized.startswith(("http://", "https://")):
        return normalized
    scheme = "https" if _is_public_host(normalized) else "http"
    return f"{scheme}://{normalized}"


def _public_ws_base_url(base_url: str) -> str:
    if base_url.startswith("https://"):
        return "wss://" + base_url.removeprefix("https://")
    if base_url.startswith("http://"):
        return "ws://" + base_url.removeprefix("http://")
    return base_url


def _integration_from_credential(
    key: str,
    label: str,
    credential: ProviderCredential | None,
    *,
    env_configured: bool,
    fallback_config: dict[str, str] | None = None,
    note: str | None = None,
) -> SetupIntegrationPublic:
    fallback_config = fallback_config or {}
    if credential:
        config = {
            config_key: str(config_value)
            for config_key, config_value in credential.config_json.items()
            if config_value not in (None, "")
        }
        return SetupIntegrationPublic(
            key=key,
            label=label,
            configured=True,
            source="database",
            editable=True,
            has_secret=credential.encrypted_api_secret is not None,
            config=config,
            note=note,
        )

    return SetupIntegrationPublic(
        key=key,
        label=label,
        configured=env_configured,
        source="environment" if env_configured else "missing",
        editable=True,
        has_secret=False,
        config=fallback_config if env_configured else {},
        note=note,
    )


def _runtime_only_integration(
    key: str,
    label: str,
    *,
    runtime_value: ResolvedRuntimeValue,
    has_secret: bool = False,
    note: str | None = None,
    config: dict[str, str] | None = None,
) -> SetupIntegrationPublic:
    return SetupIntegrationPublic(
        key=key,
        label=label,
        configured=runtime_value.configured,
        source=runtime_value.source,
        editable=True,
        has_secret=has_secret and runtime_value.configured,
        config=config or {},
        note=note,
    )


_CAPABILITY_CHANNEL: dict[ProviderCapability, str] = {
    ProviderCapability.email: "email",
    ProviderCapability.sms: "sms",
    ProviderCapability.voice: "voice",
    ProviderCapability.stt: "voice",
    ProviderCapability.tts: "voice",
    ProviderCapability.llm: "voice",
}

_REQUIRED_PROVIDER_CONFIG: dict[
    tuple[NotificationProvider, ProviderCapability],
    tuple[tuple[str, ...], ...],
] = {
    (NotificationProvider.sendgrid, ProviderCapability.email): (
        ("api_key",),
        ("from_email",),
    ),
    (NotificationProvider.smtp, ProviderCapability.email): (
        ("host",),
        ("from_email",),
    ),
    (NotificationProvider.twilio, ProviderCapability.sms): (
        ("account_sid", "api_key"),
        ("auth_token", "api_secret"),
        ("phone_number",),
    ),
    (NotificationProvider.twilio, ProviderCapability.voice): (
        ("account_sid", "api_key"),
        ("auth_token", "api_secret"),
        ("phone_number",),
    ),
    (NotificationProvider.vapi, ProviderCapability.voice): (
        ("api_key",),
        ("phone_number_id",),
        ("assistant_id",),
    ),
    (NotificationProvider.deepgram, ProviderCapability.stt): (("api_key",),),
    (NotificationProvider.deepgram, ProviderCapability.tts): (("api_key",),),
    (NotificationProvider.groq, ProviderCapability.llm): (("api_key",),),
    (NotificationProvider.openai, ProviderCapability.llm): (("api_key",),),
    (NotificationProvider.openrouter, ProviderCapability.llm): (("api_key",),),
    (NotificationProvider.together, ProviderCapability.llm): (("api_key",),),
    (NotificationProvider.ollama_local, ProviderCapability.llm): (
        ("base_url",),
        ("model",),
    ),
    (NotificationProvider.faster_whisper_local, ProviderCapability.stt): (
        ("base_url",),
        ("model",),
    ),
}

_DISPLAY_CONFIG_KEYS = {
    "account_sid",
    "base_url",
    "from_email",
    "from_name",
    "host",
    "model",
    "assistant_id",
    "call_endpoint",
    "phone_number",
    "phone_number_id",
    "port",
    "username",
}

_SENSITIVE_CONFIG_KEYS = {
    "api_key",
    "api_secret",
    "auth_token",
    "password",
    "webhook_secret",
}

_PROVIDER_CAPABILITY_NOTES: dict[tuple[NotificationProvider, ProviderCapability], str] = {
    (NotificationProvider.smtp, ProviderCapability.email): (
        "Email delivery uses the selected SMTP relay or local mail catcher."
    ),
    (NotificationProvider.faster_whisper_local, ProviderCapability.stt): (
        "Local batch transcription is configured; live voice streaming still needs a streaming STT provider."
    ),
    (NotificationProvider.ollama_local, ProviderCapability.llm): (
        "LLM responses use the configured local Ollama endpoint."
    ),
    (NotificationProvider.vapi, ProviderCapability.voice): (
        "Voice calls use the selected Vapi assistant and Vapi phone number."
    ),
}


def _catalog_entry(
    capability: ProviderCapability,
    provider: NotificationProvider,
) -> dict[str, Any]:
    for entry in PROVIDER_CATALOG.get(capability.value, []):
        if entry.get("provider") == provider.value:
            return entry
    return {
        "provider": provider.value,
        "label": provider.value.replace("_", " ").title(),
        "requires_creds": True,
        "local": False,
    }


def _has_required_provider_config(
    provider: NotificationProvider,
    capability: ProviderCapability,
    creds: dict[str, Any],
) -> bool:
    requirements = _REQUIRED_PROVIDER_CONFIG.get((provider, capability))
    if not requirements:
        return False
    return all(
        any(str(creds.get(key) or "").strip() for key in alternatives)
        for alternatives in requirements
    )


def _display_provider_config(creds: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(value)
        for key, value in creds.items()
        if key in _DISPLAY_CONFIG_KEYS
        and key not in _SENSITIVE_CONFIG_KEYS
        and value not in (None, "")
    }


def _provider_capability_integration(
    session: SessionDep,
    workspace_id: str,
    capability: ProviderCapability,
    *,
    credentials: dict[tuple[NotificationProvider, str], ProviderCredential],
    runtime_config,
) -> SetupIntegrationPublic:
    provider = resolve_active_provider(session, workspace_id, capability)
    channel = _CAPABILITY_CHANNEL[capability]
    credential = credentials.get((provider, channel))
    creds = resolve_provider_credentials(
        session,
        workspace_id=workspace_id,
        provider=provider,
        channel=channel,
    )

    source = "database" if credential else "environment"
    has_secret = bool(credential and credential.encrypted_api_secret)

    if provider == NotificationProvider.deepgram and capability in {
        ProviderCapability.stt,
        ProviderCapability.tts,
    }:
        if runtime_config.deepgram_api_key.configured:
            creds["api_key"] = runtime_config.deepgram_api_key.value
            source = runtime_config.deepgram_api_key.source
            has_secret = runtime_config.deepgram_api_key.source == "database"
    elif provider == NotificationProvider.groq and capability == ProviderCapability.llm:
        if runtime_config.groq_api_key.configured:
            creds["api_key"] = runtime_config.groq_api_key.value
            source = runtime_config.groq_api_key.source
            has_secret = runtime_config.groq_api_key.source == "database"

    configured = _has_required_provider_config(provider, capability, creds)
    if not configured:
        source = "missing"

    catalog = _catalog_entry(capability, provider)
    provider_label = str(catalog["label"])
    note = _PROVIDER_CAPABILITY_NOTES.get(
        (provider, capability),
        f"Active {capability.value} provider for this workspace.",
    )

    return SetupIntegrationPublic(
        key=capability.value,
        label=f"{capability.value.upper()}: {provider_label}",
        configured=configured,
        source=source,
        editable=True,
        has_secret=has_secret,
        config=_display_provider_config(creds) if configured else {},
        note=note,
        capability=capability,
        provider=provider,
        provider_label=provider_label,
        requires_creds=bool(catalog.get("requires_creds", True)),
        local=bool(catalog.get("local", False)),
    )


async def _redis_health(request: Request) -> bool:
    redis_manager = getattr(request.app.state, "redis_manager", None)
    if redis_manager is None:
        return False
    try:
        return await redis_manager.ping()
    except Exception:
        return False


def _worker_readiness(
    key: str,
    label: str,
    *,
    requirements: dict[str, bool],
    heartbeat: WorkerHeartbeat | None,
) -> SetupWorkerReadinessPublic:
    now = datetime.now(timezone.utc)
    missing = [name for name, configured in requirements.items() if not configured]
    running = False
    status = "not_seen"
    last_seen_at = None
    last_error_message = None

    if heartbeat is not None:
        last_seen_at = heartbeat.last_seen_at
        live_window_seconds = max(heartbeat.poll_interval_seconds * 3, 90)
        running = (now - heartbeat.last_seen_at) <= timedelta(seconds=live_window_seconds)
        status = heartbeat.status if running else "stale"
        last_error_message = heartbeat.last_error_message if heartbeat.status == "error" else None

    return SetupWorkerReadinessPublic(
        key=key,
        label=label,
        ready=not missing and running and status != "error",
        running=running,
        status=status,
        last_seen_at=last_seen_at,
        last_error_message=last_error_message,
        missing=missing,
    )


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/", response_model=HealthStatus)
async def health_check(request: Request) -> HealthStatus:
    """Health check."""
    postgres = await anyio.to_thread.run_sync(_check_postgres_sync)

    redis = False
    redis_manager = getattr(request.app.state, "redis_manager", None)
    if redis_manager is not None:
        try:
            redis = await redis_manager.ping()
        except Exception:
            redis = False

    return HealthStatus(api=True, postgres=postgres, redis=redis)


@router.get(
    "/setup-overview/",
    response_model=SetupOverviewPublic,
    dependencies=[Depends(require_admin)],
)
async def setup_overview(
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> SetupOverviewPublic:
    """Return provider and runtime readiness for the active workspace."""

    postgres = await anyio.to_thread.run_sync(_check_postgres_sync)
    redis = await _redis_health(request)
    health = HealthStatus(api=True, postgres=postgres, redis=redis)

    credentials = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.is_active == True,  # noqa: E712
        )
    ).all()
    by_provider_channel = {
        (credential.provider, credential.channel): credential for credential in credentials
    }
    runtime_config = resolve_workspace_runtime_config(session, workspace_id)
    heartbeats = {
        heartbeat.worker_key: heartbeat
        for heartbeat in session.exec(select(WorkerHeartbeat)).all()
    }

    email = _provider_capability_integration(
        session,
        workspace_id,
        ProviderCapability.email,
        credentials=by_provider_channel,
        runtime_config=runtime_config,
    )
    sms = _provider_capability_integration(
        session,
        workspace_id,
        ProviderCapability.sms,
        credentials=by_provider_channel,
        runtime_config=runtime_config,
    )
    voice = _provider_capability_integration(
        session,
        workspace_id,
        ProviderCapability.voice,
        credentials=by_provider_channel,
        runtime_config=runtime_config,
    )
    stt = _provider_capability_integration(
        session,
        workspace_id,
        ProviderCapability.stt,
        credentials=by_provider_channel,
        runtime_config=runtime_config,
    )
    tts = _provider_capability_integration(
        session,
        workspace_id,
        ProviderCapability.tts,
        credentials=by_provider_channel,
        runtime_config=runtime_config,
    )
    llm = _provider_capability_integration(
        session,
        workspace_id,
        ProviderCapability.llm,
        credentials=by_provider_channel,
        runtime_config=runtime_config,
    )
    team_notifications = _runtime_only_integration(
        "team_notifications",
        "Team Notifications",
        runtime_value=runtime_config.team_notification_email,
        note="Workspace override or environment email used for operator notifications.",
        config={"email": runtime_config.team_notification_email.value} if runtime_config.team_notification_email.configured else {},
    )

    public_base_url = _public_base_url(settings.SERVER_HOST)
    public_ws_base_url = _public_ws_base_url(public_base_url)
    callbacks = SetupCallbacksPublic(
        server_host=settings.SERVER_HOST,
        public_base_url=public_base_url,
        public_host=_is_public_host(settings.SERVER_HOST),
        sendgrid_webhook_url=f"{public_base_url}{settings.API_V1_STR}/webhooks/sendgrid",
        twilio_twiml_url=f"{public_base_url}{settings.API_V1_STR}/voice/twiml",
        twilio_status_url=f"{public_base_url}{settings.API_V1_STR}/voice/status",
        twilio_recording_url=f"{public_base_url}{settings.API_V1_STR}/voice/recording",
        twilio_media_stream_url=f"{public_ws_base_url}{settings.API_V1_STR}/voice/media-stream",
    )

    worker_readiness = [
        _worker_readiness(
            "sequence_worker",
            "Sequence worker",
            requirements={
                "postgres": postgres,
                "redis": redis,
                "email_provider": email.configured,
            },
            heartbeat=heartbeats.get("sequence_worker"),
        ),
        _worker_readiness(
            "call_worker",
            "Call worker",
            requirements={
                "postgres": postgres,
                "redis": redis,
                "voice_provider": voice.configured,
                "stt_provider": stt.configured,
                "tts_provider": tts.configured,
                "llm_provider": llm.configured,
                "public_callbacks": callbacks.public_host,
            },
            heartbeat=heartbeats.get("call_worker"),
        ),
        _worker_readiness(
            "postcall_worker",
            "Post-call worker",
            requirements={
                "postgres": postgres,
                "redis": redis,
                "email_provider": email.configured,
                "team_notifications": team_notifications.configured,
            },
            heartbeat=heartbeats.get("postcall_worker"),
        ),
        _worker_readiness(
            "ecrm_installation_projection_worker",
            "eCRM installation projection worker",
            requirements={"postgres": postgres},
            heartbeat=heartbeats.get("ecrm_installation_projection_worker"),
        ),
    ]

    return SetupOverviewPublic(
        workspace_id=workspace_id,
        health=health,
        integrations=[email, sms, voice, stt, tts, llm, team_notifications],
        worker_readiness=worker_readiness,
        callbacks=callbacks,
    )


@router.get("/live", include_in_schema=False)
async def liveness() -> dict[str, str]:
    """Kubernetes liveness probe — always 200 if the process is running."""
    return {"status": "ok"}


@router.get("/ready", include_in_schema=False)
async def readiness(request: Request) -> JSONResponse:
    """Kubernetes readiness probe — 200 only when all dependencies are reachable."""
    checks: dict[str, bool] = {}

    try:
        with engine.connect() as conn:
            conn.execute(select(1))
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False

    redis_manager = getattr(request.app.state, "redis_manager", None)
    try:
        checks["redis"] = await redis_manager.ping() if redis_manager else False
    except Exception:
        checks["redis"] = False

    all_healthy = all(checks.values())
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={"status": "ready" if all_healthy else "not_ready", "checks": checks},
    )
