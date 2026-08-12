from __future__ import annotations

import hashlib
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_SENSITIVE = {"password", "client_secret", "access_token", "authorization", "bearer", "credential", "token", "secret", "signing_key"}


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items() if key.lower() not in _SENSITIVE}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    return value


@dataclass(frozen=True)
class EvidenceRecord:
    run_id: str
    stage: str
    result_code: str
    payload_json: str
    digest: str


class EvidenceRecorder:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], EvidenceRecord] = {}

    def record(self, run_id: str, stage: str, result_code: str, payload: dict[str, Any]) -> EvidenceRecord:
        key = (run_id, stage, result_code)
        if key in self._records:
            return self._records[key]
        serialized = json.dumps(redact_payload(payload), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        record = EvidenceRecord(run_id, stage, result_code, serialized, digest)
        self._records[key] = record
        return record

    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda record: (record.run_id, record.stage, record.result_code)))


def _b64(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class EvidenceBundle:
    """Portable, secret-free evidence manifest signed outside tenant configuration."""

    tenant_key: str
    canonical_payload: str
    public_key: str
    signature: str

    @classmethod
    def from_recorder(cls, tenant_key: str, recorder: EvidenceRecorder, signer: Ed25519PrivateKey) -> EvidenceBundle:
        return cls.from_records(tenant_key, recorder.records(), signer)

    @classmethod
    def from_records(cls, tenant_key: str, records: tuple[EvidenceRecord, ...], signer: Ed25519PrivateKey) -> EvidenceBundle:
        payload = {
            "schema_version": "phase1.evidence.v1",
            "tenant_key": tenant_key,
            "records": [
                {"run_id": record.run_id, "stage": record.stage, "result_code": record.result_code, "payload": json.loads(record.payload_json), "digest": record.digest}
                for record in records
            ],
        }
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        public_key = signer.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return cls(tenant_key, canonical_payload, _b64(public_key), _b64(signer.sign(canonical_payload.encode("utf-8"))))

    def verify(self) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(_unb64(self.public_key)).verify(_unb64(self.signature), self.canonical_payload.encode("utf-8"))
        except (InvalidSignature, ValueError):
            return False
        return True
