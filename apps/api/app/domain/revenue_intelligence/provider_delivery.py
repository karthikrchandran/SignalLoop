"""Configured provider delivery for RevenueOS interventions."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.domain_models import ProviderCapability
from app.infrastructure.providers.registry import (
    ProviderResolutionError,
    get_strict_adapter,
)

from .dispatcher import InterventionDeliveryResult


class ConfiguredEmailInterventionDelivery:
    """Deliver approved email interventions through configured provider state."""

    def __init__(self, *, session: Session, workspace_id: str) -> None:
        self.session = session
        self.workspace_id = workspace_id

    async def deliver(
        self, *, action: str, payload: dict[str, object], idempotency_key: str
    ) -> InterventionDeliveryResult:
        if action != "send_email":
            return InterventionDeliveryResult(
                provider="validation",
                accepted=False,
                retryable=False,
                receipt={"action": action},
                reason="UNSUPPORTED_ACTION",
            )

        message = _email_payload(payload)
        if message is None:
            return InterventionDeliveryResult(
                provider="validation",
                accepted=False,
                retryable=False,
                receipt={"action": action},
                reason="INVALID_ACTION_PAYLOAD",
            )

        try:
            adapter = get_strict_adapter(
                self.session,
                workspace_id=self.workspace_id,
                capability=ProviderCapability.email,
            )
        except ProviderResolutionError as exc:
            return InterventionDeliveryResult(
                provider="configuration",
                accepted=False,
                retryable=False,
                receipt={"error": str(exc)},
                reason="PROVIDER_CONFIGURATION_REQUIRED",
            )

        result = await adapter.send_email(
            to=message["to"],
            subject=message["subject"],
            body_text=message["body_text"],
            body_html=message["body_html"],
            idempotency_key=idempotency_key,
        )
        status_code = _status_code(result)
        accepted = status_code in {200, 201, 202}
        return InterventionDeliveryResult(
            provider="email",
            accepted=accepted,
            retryable=status_code == 429 or status_code >= 500,
            receipt=result,
            reason=None if accepted else "PROVIDER_REJECTED",
        )


def _email_payload(payload: dict[str, object]) -> dict[str, str] | None:
    values: dict[str, str] = {}
    for key in ("to", "subject", "body_text", "body_html"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        values[key] = value.strip()
    return values


def _status_code(result: dict[str, Any]) -> int:
    raw = result.get("status_code")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdecimal():
        return int(raw)
    return 0
