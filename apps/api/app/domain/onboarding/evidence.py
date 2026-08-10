from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

_SENSITIVE = {"password", "client_secret", "access_token", "authorization", "bearer"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items() if key.lower() not in _SENSITIVE}
    if isinstance(value, list):
        return [_redact(item) for item in value]
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
        serialized = json.dumps(_redact(payload), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        record = EvidenceRecord(run_id, stage, result_code, serialized, digest)
        self._records[key] = record
        return record
