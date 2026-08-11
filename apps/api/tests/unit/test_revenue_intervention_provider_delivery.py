from __future__ import annotations

import asyncio

from sqlmodel import Session, SQLModel, create_engine

from app.domain.revenue_intelligence import provider_delivery as delivery_module
from app.domain.revenue_intelligence.provider_delivery import (
    ConfiguredEmailInterventionDelivery,
)
from app.domain_models import ProviderCapability
from app.infrastructure.providers.registry import ProviderResolutionError


class CapturingEmailAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_email(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"status_code": 202, "message_id": "sg-1"}


def test_provider_delivery_uses_strict_email_adapter(
    monkeypatch,
) -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    adapter = CapturingEmailAdapter()
    captured: dict[str, object] = {}

    def fake_strict_adapter(session, *, workspace_id: str, capability: ProviderCapability):
        captured["session"] = session
        captured["workspace_id"] = workspace_id
        captured["capability"] = capability
        return adapter

    monkeypatch.setattr(delivery_module, "get_strict_adapter", fake_strict_adapter)

    with Session(engine) as session:
        result = asyncio.run(
            ConfiguredEmailInterventionDelivery(
                session=session,
                workspace_id="ws-ara",
            ).deliver(
                action="send_email",
                payload={
                    "to": "owner@example.test",
                    "subject": "Review account",
                    "body_text": "Review account A.",
                    "body_html": "<p>Review account A.</p>",
                },
                idempotency_key="dispatch-1",
            )
        )

    assert captured["workspace_id"] == "ws-ara"
    assert captured["capability"] == ProviderCapability.email
    assert result.accepted is True
    assert result.provider == "email"
    assert result.receipt == {"status_code": 202, "message_id": "sg-1"}
    assert adapter.calls == [
        {
            "to": "owner@example.test",
            "subject": "Review account",
            "body_text": "Review account A.",
            "body_html": "<p>Review account A.</p>",
            "idempotency_key": "dispatch-1",
        }
    ]


def test_provider_delivery_configuration_error_is_non_retryable(monkeypatch) -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    def fake_strict_adapter(_session, *, workspace_id: str, capability: ProviderCapability):
        assert workspace_id == "ws-ara"
        assert capability == ProviderCapability.email
        raise ProviderResolutionError("No active credentials")

    monkeypatch.setattr(delivery_module, "get_strict_adapter", fake_strict_adapter)

    with Session(engine) as session:
        result = asyncio.run(
            ConfiguredEmailInterventionDelivery(session=session, workspace_id="ws-ara").deliver(
                action="send_email",
                payload={
                    "to": "owner@example.test",
                    "subject": "Review account",
                    "body_text": "Review account A.",
                    "body_html": "<p>Review account A.</p>",
                },
                idempotency_key="dispatch-1",
            )
        )

    assert result.accepted is False
    assert result.retryable is False
    assert result.provider == "configuration"
    assert result.reason == "PROVIDER_CONFIGURATION_REQUIRED"
    assert result.receipt == {"error": "No active credentials"}


def test_provider_delivery_rejects_malformed_action_payload() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        result = asyncio.run(
            ConfiguredEmailInterventionDelivery(session=session, workspace_id="ws-ara").deliver(
                action="send_email",
                payload={"to": "owner@example.test", "subject": "Missing bodies"},
                idempotency_key="dispatch-1",
            )
        )

    assert result.accepted is False
    assert result.retryable is False
    assert result.provider == "validation"
    assert result.reason == "INVALID_ACTION_PAYLOAD"


def test_provider_delivery_rejects_unsupported_action() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        result = asyncio.run(
            ConfiguredEmailInterventionDelivery(session=session, workspace_id="ws-ara").deliver(
                action="make_call",
                payload={"to": "+15551234567"},
                idempotency_key="dispatch-1",
            )
        )

    assert result.accepted is False
    assert result.retryable is False
    assert result.provider == "validation"
    assert result.reason == "UNSUPPORTED_ACTION"
