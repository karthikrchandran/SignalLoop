"""Provider-neutral eCRM proposal command and receipt contract."""

from __future__ import annotations

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
