"""Bound eCRM cell client; callers cannot provide destination authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from app.domain.ecrm_installations.models import utc_now
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.secrets import SecretResolver


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass(frozen=True)
class CellDeliveryResponse:
    status_code: int
    body: dict[str, Any]


class CellTransport(Protocol):
    def post(self, url: str, *, json: dict[str, Any], headers: dict[str, str], timeout: float) -> CellDeliveryResponse: ...


class HttpxCellTransport:
    def post(self, url: str, *, json: dict[str, Any], headers: dict[str, str], timeout: float) -> CellDeliveryResponse:
        response = httpx.post(url, json=json, headers=headers, timeout=timeout)
        try:
            body = response.json()
        except ValueError:
            body = {}
        return CellDeliveryResponse(response.status_code, body)


class EcrmCellUnavailable(RuntimeError):
    pass


class EcrmCellClient:
    def __init__(
        self,
        repository: EcrmInstallationRepository,
        secrets: SecretResolver,
        transport: CellTransport,
        *,
        circuit_threshold: int = 5,
    ) -> None:
        self.repository = repository
        self.secrets = secrets
        self.transport = transport
        self.circuit_threshold = circuit_threshold

    def send(
        self,
        *,
        workspace_id: str,
        source_event_id: str,
        source_version: int,
        event_kind: str,
        stream_key: str,
        payload: dict[str, Any],
        correlation_id: str,
        deadline_seconds: float = 15.0,
    ) -> CellDeliveryResponse:
        binding = self.repository.get_binding(workspace_id)
        if binding is None or binding.status == "SUSPENDED":
            raise EcrmCellUnavailable("workspace has no active eCRM installation")
        circuit_open_until = _aware(binding.circuit_open_until)
        if circuit_open_until is not None and circuit_open_until > utc_now():
            raise EcrmCellUnavailable("eCRM installation circuit is open")
        token = self.secrets.resolve(binding.credential_secret_ref)
        try:
            response = self.transport.post(
                f"{binding.base_url.rstrip('/')}/api/integrations/signalloop/deliveries",
                json={
                    "source_event_id": source_event_id,
                    "source_version": source_version,
                    "event_kind": event_kind,
                    "stream_key": stream_key,
                    "payload": payload,
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": source_event_id,
                    "X-Correlation-Id": correlation_id,
                    "X-ECRM-Cell-Id": binding.ecrm_cell_id,
                    "X-ECRM-Cell-Key": binding.ecrm_cell_key,
                },
                timeout=deadline_seconds,
            )
        except (httpx.HTTPError, OSError):
            binding.consecutive_failures += 1
            if binding.consecutive_failures >= self.circuit_threshold:
                from datetime import timedelta

                binding.status = "DEGRADED"
                binding.circuit_open_until = utc_now() + timedelta(minutes=1)
            binding.updated_at = utc_now()
            self.repository.session.add(binding)
            self.repository.session.commit()
            raise
        binding.consecutive_failures = 0
        binding.circuit_open_until = None
        if binding.status == "DEGRADED":
            binding.status = "ACTIVE"
        binding.verified_at = utc_now()
        binding.updated_at = utc_now()
        self.repository.session.add(binding)
        self.repository.session.commit()
        return response
