"""Provider-neutral eCRM proposal command and receipt contract."""

from __future__ import annotations

import importlib
import os
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class EcrmProposalCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "proposal-command.v1"
    command_key: str
    ecrm_cell_id: str
    client_account_id: str
    proposal_id: str
    mode: str
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload: dict[str, Any]


class EcrmProposalReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "proposal-receipt.v1"
    command_key: str
    ecrm_cell_id: str
    client_account_id: str
    proposal_id: str
    version_id: str
    version_number: int = Field(ge=1)
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    receipt_id: str


class EcrmProposalApprovalReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "proposal-approval-receipt.v1"
    ecrm_cell_id: str
    proposal_id: str
    version_id: str
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval_id: str
    approved_by: str


class EcrmProposalAdapter(Protocol):
    def apply(self, command: EcrmProposalCommand) -> EcrmProposalReceipt: ...

    def lookup_receipt(self, command_key: str) -> EcrmProposalReceipt | None: ...


class EcrmProposalAdapterConfigurationError(RuntimeError):
    """No deployment-owned eCRM proposal adapter is configured."""


def load_ecrm_proposal_adapter() -> EcrmProposalAdapter:
    """Load a deployment-owned adapter factory from ``module:callable`` config."""

    reference = os.environ.get("ECRM_PROPOSAL_ADAPTER_FACTORY", "").strip()
    if ":" not in reference:
        raise EcrmProposalAdapterConfigurationError(
            "ECRM_PROPOSAL_ADAPTER_FACTORY must be configured as module:callable"
        )
    module_name, callable_name = reference.split(":", 1)
    factory = getattr(importlib.import_module(module_name), callable_name, None)
    if not callable(factory):
        raise EcrmProposalAdapterConfigurationError(
            "eCRM proposal adapter factory is invalid"
        )
    adapter = factory()
    if not all(
        callable(getattr(adapter, name, None)) for name in ("apply", "lookup_receipt")
    ):
        raise EcrmProposalAdapterConfigurationError(
            "eCRM proposal adapter contract is incomplete"
        )
    return adapter
