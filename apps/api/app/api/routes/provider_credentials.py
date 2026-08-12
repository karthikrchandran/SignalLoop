"""API route: POST /workspaces/{workspace_id}/provider-credentials

Workspace admins use this endpoint to store provider API keys.
Keys are encrypted with Fernet (AES-128-CBC + HMAC) before being written to
the database.  The plaintext is never logged or returned to the caller.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.core.encryption import encrypt
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain_models import (
    NotificationProvider,
    ProviderCapability,
    ProviderCredential,
    WorkspaceProviderSelection,
)
from app.infrastructure.providers.registry import (
    PROVIDER_CATALOG,
    ProviderResolutionError,
    build_adapter_from_credential,
)

router = APIRouter(
    prefix="/workspaces",
    tags=["provider-credentials"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ProviderCredentialCreate(BaseModel):
    """Request payload for creating provider credential."""

    provider: NotificationProvider
    channel: str = Field(
        max_length=32,
        description="e.g. 'email', 'sms', 'voice', 'scheduling'",
    )
    api_key: str = Field(description="Provider API key — stored encrypted")
    api_secret: str | None = Field(
        default=None,
        description="Optional secondary secret (e.g. auth token, webhook secret)",
    )
    config_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra provider config (from_email, phone_number, …)",
    )


class ProviderCredentialPublic(BaseModel):
    """API response model: provider credential."""

    id: uuid.UUID
    workspace_id: str
    provider: NotificationProvider
    channel: str
    has_api_secret: bool
    config_json: dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


class ProviderCredentialsPublic(BaseModel):
    """API response model: provider credentials."""

    data: list[ProviderCredentialPublic]
    count: int


def _ensure_workspace_path_matches_header(
    workspace_id: str, workspace_header: str
) -> None:
    if workspace_id != workspace_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUTH_ERROR", "semantic": "AUTH_ERROR"}},
        )


SENSITIVE_CONFIG_KEYS = {
    "apikey",
    "api_key",
    "apisecret",
    "api_secret",
    "authtoken",
    "auth_token",
    "password",
    "privatekey",
    "private_key",
    "secret",
    "token",
    "webhooksecret",
    "webhook_secret",
}


def _normalized_config_key(key: str) -> str:
    return key.lower().replace("-", "_").replace(" ", "_")


def _is_sensitive_config_key(key: str) -> bool:
    normalized = _normalized_config_key(key)
    compact = normalized.replace("_", "")
    return (
        normalized in SENSITIVE_CONFIG_KEYS
        or compact in SENSITIVE_CONFIG_KEYS
        or normalized.endswith("_secret")
        or normalized.endswith("_token")
        or compact.endswith("secret")
        or compact.endswith("token")
    )


def _find_sensitive_config_keys(config: dict[str, Any], prefix: str = "") -> list[str]:
    found: list[str] = []
    for key, value in config.items():
        path = f"{prefix}.{key}" if prefix else key
        if _is_sensitive_config_key(key):
            found.append(path)
        if isinstance(value, dict):
            found.extend(_find_sensitive_config_keys(value, path))
    return found


def _safe_config_json(config: dict[str, Any]) -> dict[str, Any]:
    sensitive_keys = _find_sensitive_config_keys(config)
    if sensitive_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": "SENSITIVE_CONFIG_KEY",
                    "message": "Store secrets in api_key/api_secret, not config_json",
                    "semantic": "POLICY_VIOLATION",
                    "details": {"keys": sensitive_keys},
                }
            },
        )
    return config


def _public_config_json(config: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in config.items():
        if _is_sensitive_config_key(key):
            redacted[key] = "[redacted]"
        elif isinstance(value, dict):
            redacted[key] = _public_config_json(value)
        else:
            redacted[key] = value
    return redacted


def _ensure_provider_supported_for_capability(
    capability: ProviderCapability,
    provider: NotificationProvider,
) -> None:
    supported = {
        option["provider"] for option in PROVIDER_CATALOG.get(capability.value, [])
    }
    if provider.value in supported:
        return

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "error": {
                "code": "UNSUPPORTED_PROVIDER_CAPABILITY",
                "message": (
                    f"Provider '{provider.value}' is not supported for "
                    f"capability '{capability.value}'"
                ),
                "semantic": "POLICY_VIOLATION",
                "details": {
                    "capability": capability.value,
                    "provider": provider.value,
                    "supported_providers": sorted(supported),
                },
            }
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/{workspace_id}/provider-credentials",
    response_model=ProviderCredentialPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Store provider credentials for a workspace",
)
async def upsert_provider_credentials(
    *,
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    current_user: CurrentUser,
    session: SessionDep,
    body: ProviderCredentialCreate,
    request: Request,
    idempotency_key: IdempotencyKeyDep,
) -> ProviderCredentialPublic:
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="provider-credential-upsert",
        request_payload=body.model_dump(mode="json"),
        mutation=lambda: _upsert_provider_credentials_once(
            workspace_id=workspace_id,
            workspace_header=workspace_header,
            current_user=current_user,
            session=session,
            body=body,
        ),
    )


def _upsert_provider_credentials_once(
    *,
    workspace_id: str,
    workspace_header: str,
    current_user: CurrentUser,
    session: SessionDep,
    body: ProviderCredentialCreate,
) -> ProviderCredentialPublic:
    """Create or replace the active credential for a given provider+channel pair.

    The ``api_key`` (and optional ``api_secret``) are encrypted with Fernet
    before being persisted.  The response **never** includes the plaintext key.
    """
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    if not body.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="api_key must not be empty",
        )
    config_json = _safe_config_json(body.config_json)

    # Deactivate any existing credential for this workspace+provider+channel
    existing = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == body.provider,
            ProviderCredential.channel == body.channel,
            ProviderCredential.is_active == True,  # noqa: E712
        )
    ).all()
    for cred in existing:
        cred.is_active = False
        session.add(cred)

    cred = ProviderCredential(
        workspace_id=workspace_id,
        provider=body.provider,
        channel=body.channel,
        encrypted_api_key=encrypt(body.api_key),
        encrypted_api_secret=encrypt(body.api_secret) if body.api_secret else None,
        config_json=config_json,
        is_active=True,
    )
    session.add(cred)
    append_audit_event_to_session(
        session,
        event_name="provider_credential_upserted",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="provider_credential",
        resource_id=str(cred.id),
        payload={
            "credential_id": str(cred.id),
            "provider": body.provider.value,
            "channel": body.channel,
            "has_api_secret": body.api_secret is not None,
            "deactivated_existing_count": len(existing),
        },
    )
    session.commit()
    session.refresh(cred)

    return ProviderCredentialPublic(
        id=cred.id,
        workspace_id=cred.workspace_id,
        provider=cred.provider,
        channel=cred.channel,
        has_api_secret=cred.encrypted_api_secret is not None,
        config_json=_public_config_json(cred.config_json),
        is_active=cred.is_active,
    )


@router.get(
    "/{workspace_id}/provider-credentials",
    response_model=ProviderCredentialsPublic,
    dependencies=[Depends(require_admin)],
    summary="List active provider credentials for a workspace",
)
def list_provider_credentials(
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    session: SessionDep,
) -> ProviderCredentialsPublic:
    """Return metadata for all active credentials.  Plaintext keys are never exposed."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    rows = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.is_active == True,  # noqa: E712
        )
    ).all()

    return ProviderCredentialsPublic(
        data=[
            ProviderCredentialPublic(
                id=r.id,
                workspace_id=r.workspace_id,
                provider=r.provider,
                channel=r.channel,
                has_api_secret=r.encrypted_api_secret is not None,
                config_json=_public_config_json(r.config_json),
                is_active=r.is_active,
            )
            for r in rows
        ],
        count=len(rows),
    )


@router.delete(
    "/{workspace_id}/provider-credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Deactivate a stored credential",
)
async def deactivate_provider_credential(
    workspace_id: str,
    credential_id: uuid.UUID,
    workspace_header: WorkspaceIdDep,
    current_user: CurrentUser,
    session: SessionDep,
    request: Request,
    idempotency_key: IdempotencyKeyDep,
) -> None:
    await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="provider-credential-deactivate",
        request_payload={"credential_id": str(credential_id)},
        mutation=lambda: _deactivate_provider_credential_once(
            workspace_id, credential_id, workspace_header, current_user, session
        ),
    )


def _deactivate_provider_credential_once(
    workspace_id: str,
    credential_id: uuid.UUID,
    workspace_header: str,
    current_user: CurrentUser,
    session: SessionDep,
) -> None:
    """Deactivate provider credential."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    cred = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.workspace_id == workspace_id,
        )
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    cred.is_active = False
    session.add(cred)
    append_audit_event_to_session(
        session,
        event_name="provider_credential_deactivated",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="provider_credential",
        resource_id=str(cred.id),
        payload={
            "credential_id": str(cred.id),
            "provider": cred.provider.value,
            "channel": cred.channel,
        },
    )
    session.commit()


# ---------------------------------------------------------------------------
# Provider catalog + per-workspace selection
# ---------------------------------------------------------------------------


class ProviderOption(BaseModel):
    provider: NotificationProvider
    label: str
    requires_creds: bool
    free_tier: str | None = None
    local: bool = False


class CapabilityOptions(BaseModel):
    capability: ProviderCapability
    providers: list[ProviderOption]


class ProviderCatalogPublic(BaseModel):
    data: list[CapabilityOptions]


@router.get(
    "/{workspace_id}/provider-options",
    response_model=ProviderCatalogPublic,
    dependencies=[Depends(require_admin)],
    summary="List the supported providers for each capability",
)
def list_provider_options(
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
) -> ProviderCatalogPublic:
    """Return the full catalog of {capability → providers} the platform supports.

    Workspaces use this to render a "choose your provider" UI.
    """
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    return ProviderCatalogPublic(
        data=[
            CapabilityOptions(
                capability=ProviderCapability(cap),
                providers=[ProviderOption(**p) for p in providers],
            )
            for cap, providers in PROVIDER_CATALOG.items()
        ]
    )


class ProviderSelectionUpsert(BaseModel):
    capability: ProviderCapability
    provider: NotificationProvider


class ProviderSelectionPublic(BaseModel):
    id: uuid.UUID
    workspace_id: str
    capability: ProviderCapability
    provider: NotificationProvider
    is_active: bool

    model_config = {"from_attributes": True}


class ProviderSelectionsPublic(BaseModel):
    data: list[ProviderSelectionPublic]
    count: int


@router.get(
    "/{workspace_id}/provider-selection",
    response_model=ProviderSelectionsPublic,
    dependencies=[Depends(require_admin)],
    summary="List the workspace's active provider selections",
)
def list_provider_selections(
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    session: SessionDep,
) -> ProviderSelectionsPublic:
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    rows = session.exec(
        select(WorkspaceProviderSelection).where(
            WorkspaceProviderSelection.workspace_id == workspace_id,
            WorkspaceProviderSelection.is_active == True,  # noqa: E712
        )
    ).all()
    return ProviderSelectionsPublic(
        data=[ProviderSelectionPublic.model_validate(r) for r in rows],
        count=len(rows),
    )


@router.put(
    "/{workspace_id}/provider-selection",
    response_model=ProviderSelectionPublic,
    dependencies=[Depends(require_admin)],
    summary="Choose which provider to use for a capability in this workspace",
)
async def upsert_provider_selection(
    *,
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    current_user: CurrentUser,
    session: SessionDep,
    body: ProviderSelectionUpsert,
    request: Request,
    idempotency_key: IdempotencyKeyDep,
) -> ProviderSelectionPublic:
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="provider-selection-upsert",
        request_payload=body.model_dump(mode="json"),
        mutation=lambda: _upsert_provider_selection_once(
            workspace_id, workspace_header, current_user, session, body
        ),
    )


def _upsert_provider_selection_once(
    workspace_id: str,
    workspace_header: str,
    current_user: CurrentUser,
    session: SessionDep,
    body: ProviderSelectionUpsert,
) -> ProviderSelectionPublic:
    """Upsert the active provider for ``capability`` in this workspace.

    Subsequent worker runs will dispatch to the chosen provider via the
    registry.  Workspace admins must separately store credentials via
    ``POST /provider-credentials`` (unless the provider is purely local).
    """
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    _ensure_provider_supported_for_capability(body.capability, body.provider)
    existing = session.exec(
        select(WorkspaceProviderSelection).where(
            WorkspaceProviderSelection.workspace_id == workspace_id,
            WorkspaceProviderSelection.capability == body.capability,
        )
    ).first()
    if existing:
        existing.provider = body.provider
        existing.is_active = True
        session.add(existing)
        row = existing
    else:
        row = WorkspaceProviderSelection(
            workspace_id=workspace_id,
            capability=body.capability,
            provider=body.provider,
            is_active=True,
        )
        session.add(row)
    append_audit_event_to_session(
        session,
        event_name="provider_selection_upserted",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="provider_selection",
        resource_id=str(row.id) if row.id else None,
        payload={
            "capability": body.capability.value,
            "provider": body.provider.value,
        },
    )
    session.commit()
    session.refresh(row)
    return ProviderSelectionPublic.model_validate(row)


class ProviderCredentialTestResult(BaseModel):
    ok: bool
    provider: NotificationProvider
    channel: str
    detail: str | None = None


@router.post(
    "/{workspace_id}/provider-credentials/{credential_id}/test",
    response_model=ProviderCredentialTestResult,
    dependencies=[Depends(require_admin)],
    summary="Smoke-test a stored credential by instantiating its adapter",
)
def test_provider_credential(
    workspace_id: str,
    credential_id: uuid.UUID,
    workspace_header: WorkspaceIdDep,
    session: SessionDep,
) -> ProviderCredentialTestResult:
    """Lightweight probe: resolve the adapter for the stored credential.

    This only verifies that the credential can be decrypted and an adapter can
    be constructed — it does not perform a real send/call.  Real send tests
    should be added per-provider in a follow-up to avoid surprise charges.
    """
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    cred = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.is_active == True,  # noqa: E712
        )
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    # Map channel -> capability for adapter construction.
    channel_to_capability = {
        "email": ProviderCapability.email,
        "sms": ProviderCapability.sms,
        "voice": ProviderCapability.voice,
        "stt": ProviderCapability.stt,
        "tts": ProviderCapability.tts,
        "llm": ProviderCapability.llm,
    }
    capability = channel_to_capability.get(cred.channel)
    if capability is None:
        return ProviderCredentialTestResult(
            ok=False,
            provider=cred.provider,
            channel=cred.channel,
            detail=f"Channel '{cred.channel}' has no adapter capability mapping",
        )

    try:
        adapter = build_adapter_from_credential(
            session,
            workspace_id=workspace_id,
            provider=cred.provider,
            capability=capability,
        )
        return ProviderCredentialTestResult(
            ok=True,
            provider=cred.provider,
            channel=cred.channel,
            detail=f"Resolved {type(adapter).__name__}",
        )
    except ProviderResolutionError as exc:
        return ProviderCredentialTestResult(
            ok=False,
            provider=cred.provider,
            channel=cred.channel,
            detail=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        return ProviderCredentialTestResult(
            ok=False,
            provider=cred.provider,
            channel=cred.channel,
            detail=str(exc),
        )
