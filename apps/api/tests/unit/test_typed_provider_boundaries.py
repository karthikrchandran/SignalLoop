"""Runtime contract coverage for dynamically loaded and persisted values."""

import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.api.routes.kpis import _get_cached
from app.domain.proposal_agent.ecrm_adapter import (
    EcrmProposalAdapterConfigurationError,
    load_ecrm_proposal_adapter,
)
from app.domain.revenue_intelligence.dispatcher import InterventionAttemptEnvelope
from app.domain.scheduling.providers import (
    CalendarProviderConfigurationError,
    load_calendar_provider,
)


@pytest.mark.parametrize("kind", ["calendar", "proposal"])
@pytest.mark.parametrize("valid", [False, True])
def test_dynamic_provider_factories_validate_callable_contracts(
    monkeypatch: pytest.MonkeyPatch, kind: str, valid: bool,
) -> None:
    methods = (
        ("free_busy", "create_event", "reschedule_event", "cancel_event", "lookup_event")
        if kind == "calendar" else ("apply", "lookup_receipt")
    )
    provider = SimpleNamespace(**{name: lambda *args, **kwargs: None for name in methods})
    if not valid:
        setattr(provider, methods[0], None)
    module = ModuleType("_signalloop_typed_boundary_factory")
    module.create = lambda: provider
    monkeypatch.setitem(sys.modules, module.__name__, module)
    variable = "CALENDAR_PROVIDER_FACTORY" if kind == "calendar" else "ECRM_PROPOSAL_ADAPTER_FACTORY"
    monkeypatch.setenv(variable, f"{module.__name__}:create")
    loader = load_calendar_provider if kind == "calendar" else load_ecrm_proposal_adapter
    error = CalendarProviderConfigurationError if kind == "calendar" else EcrmProposalAdapterConfigurationError
    if valid:
        assert loader() is provider
    else:
        with pytest.raises(error):
            loader()


@pytest.mark.parametrize("payload", [None, [], 7, "not an object", False])
def test_kpi_cache_rejects_non_object_json(payload: object) -> None:
    client = SimpleNamespace(get=AsyncMock(return_value=json.dumps(payload)))
    app = SimpleNamespace(state=SimpleNamespace(redis_manager=SimpleNamespace(client=client)))
    request = Request({"type": "http", "app": app})
    assert asyncio.run(_get_cached(request, "synthetic-cache-key")) is None


@pytest.mark.parametrize("invalid_refs", [None, "release-1", 42, {}])
def test_persisted_intervention_rejects_invalid_reference_collections(
    invalid_refs: object,
) -> None:
    original = InterventionAttemptEnvelope(
        attempt_id=uuid4(), intervention_id=uuid4(), workspace_id="typed-boundary",
        channel="email", destination_ref="synthetic-contact", policy_decision_ref="policy-1",
        knowledge_release_refs=("release-1",), idempotency_key="test-key",
        scheduled_for=datetime.now(timezone.utc), action="send_email",
        action_payload_json="{}",
    )
    persisted = asdict(original)
    assert InterventionAttemptEnvelope.from_persisted(persisted) == original
    persisted["knowledge_release_refs"] = invalid_refs
    with pytest.raises(ValueError, match="knowledge release refs"):
        InterventionAttemptEnvelope.from_persisted(persisted)
