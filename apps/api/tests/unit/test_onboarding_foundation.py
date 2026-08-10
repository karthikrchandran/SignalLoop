from app.domain.onboarding.manifest import load_phase1_manifests
from app.domain.onboarding.models import OnboardingStage, StageStatus, can_transition
from app.domain.onboarding.providers import FakeProviderHub, ProviderEgressError
from app.domain.onboarding.service import InMemoryOnboardingService


def test_stage_transition_table() -> None:
    assert can_transition(StageStatus.PENDING, StageStatus.RUNNING)
    assert can_transition(StageStatus.RUNNING, StageStatus.SUCCEEDED)
    assert can_transition(StageStatus.RUNNING, StageStatus.FAILED)
    assert not can_transition(StageStatus.SUCCEEDED, StageStatus.RUNNING)


def test_phase1_manifests_only_include_supported_launch_tenants() -> None:
    manifests = load_phase1_manifests()
    assert set(manifests) == {"ara-global", "ai-consulting"}
    assert all(
        set(manifest.products) == {"commitarc", "revenueos", "signalloop"}
        for manifest in manifests.values()
    )
    assert "haloehs" not in manifests


def test_retry_is_idempotent_and_preserves_completed_stages() -> None:
    providers = FakeProviderHub()
    service = InMemoryOnboardingService(providers)
    first = service.run("ara-global", fail_at=OnboardingStage.NATIVE_INTEGRATION_VERIFIED)
    assert first.status == StageStatus.FAILED
    assert first.stages[OnboardingStage.TENANT_DRAFTED].status == StageStatus.SUCCEEDED
    second = service.retry(first.run_id)
    assert second.status == StageStatus.SUCCEEDED
    assert service.count_tenants("ara-global") == 1
    assert service.count_entitlements("ara-global") == 3
    assert providers.calls.count("tenant:ara-global") == 1


def test_fake_provider_refuses_non_loopback_egress() -> None:
    hub = FakeProviderHub()
    try:
        hub.request("https://provider.example.test/send")
    except ProviderEgressError:
        pass
    else:
        raise AssertionError("fake provider must reject external egress")
    assert hub.calls == []
