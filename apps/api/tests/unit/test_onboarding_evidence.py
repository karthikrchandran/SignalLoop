from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.domain.onboarding.evidence import EvidenceBundle, EvidenceRecorder


def test_evidence_is_redacted_and_idempotent() -> None:
    recorder = EvidenceRecorder()
    first = recorder.record("run-1", "TENANT_DRAFTED", "CREATED", {"password": "secret", "tenant": "ara-global"})
    second = recorder.record("run-1", "TENANT_DRAFTED", "CREATED", {"password": "other"})
    assert first == second
    assert "secret" not in first.payload_json
    assert "password" not in first.payload_json.lower()


def test_signed_evidence_bundle_verifies_and_never_exports_secret_values() -> None:
    signer = Ed25519PrivateKey.generate()
    recorder = EvidenceRecorder()
    recorder.record(
        "run-1", "NATIVE_INTEGRATION_VERIFIED", "CANARY_OK",
        {"tenant": "ara-global", "client_secret": "do-not-export", "reconciliation": {"missing": 0}},
    )

    bundle = EvidenceBundle.from_recorder("ara-global", recorder, signer)

    assert bundle.verify()
    assert "do-not-export" not in bundle.canonical_payload
    assert "client_secret" not in bundle.canonical_payload
