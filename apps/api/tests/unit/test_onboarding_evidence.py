from app.domain.onboarding.evidence import EvidenceRecorder


def test_evidence_is_redacted_and_idempotent() -> None:
    recorder = EvidenceRecorder()
    first = recorder.record("run-1", "TENANT_DRAFTED", "CREATED", {"password": "secret", "tenant": "ara-global"})
    second = recorder.record("run-1", "TENANT_DRAFTED", "CREATED", {"password": "other"})
    assert first == second
    assert "secret" not in first.payload_json
    assert "password" not in first.payload_json.lower()
