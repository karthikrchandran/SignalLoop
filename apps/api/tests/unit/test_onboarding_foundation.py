import pytest

from app.domain.onboarding.fixtures import phase1_dry_run_fixtures
from app.domain.onboarding.manifest import (
    TenantManifest,
    load_phase1_manifests,
    validate_manifest,
)
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


def test_phase1_manifests_are_versioned_and_contain_only_secret_references() -> None:
    manifests = load_phase1_manifests()
    for manifest in manifests.values():
        validate_manifest(manifest)
        assert manifest.schema_version == "phase1.v1"
        assert manifest.product_editions["revenueos"]
        assert manifest.compliance_packs
        assert all("=" not in reference for reference in manifest.secret_refs)


def test_manifest_rejects_inline_secret_and_unsupported_product() -> None:
    manifest = TenantManifest(
        key="tenant-test", legal_name="Tenant Test", display_name="Tenant Test",
        region="US", locale="en-US", timezone="America/New_York", currency="USD",
        products=("revenueos", "unknown"), product_editions={"revenueos": "enterprise"},
        compliance_packs=("us-consent",), owner_email="owner@tenant.test",
        allowed_email_domains=("tenant.test",), admin_role_bundles=("TENANT_OWNER",),
        secret_refs=("provider.client_secret=not-allowed",), consent_policy="us-consent-required",
        branding_mode="neutral",
    )
    with pytest.raises(ValueError, match="inline secret|unsupported product"):
        validate_manifest(manifest)


def test_manifest_requires_explicit_region_locale_currency_and_channel_policy() -> None:
    manifest = TenantManifest(
        key="tenant-test", legal_name="Tenant Test", display_name="Tenant Test",
        region="GB", locale="en-US", timezone="America/New_York", currency="USD",
        products=("revenueos",), product_editions={"revenueos": "enterprise"},
        compliance_packs=("us-consent",), channels=("email", "unapproved-channel"),
        owner_email="owner@tenant.test", allowed_email_domains=("tenant.test",),
        admin_role_bundles=("TENANT_OWNER",), secret_refs=("provider.client",),
        consent_policy="us-consent-required", branding_mode="neutral",
    )
    with pytest.raises(ValueError, match="region|channel"):
        validate_manifest(manifest)


def test_dry_run_fixtures_cover_launch_tenants_and_halo_rejection() -> None:
    fixtures = phase1_dry_run_fixtures()
    assert fixtures["ara-global"].expected_status == "READY_FOR_ACCEPTANCE"
    assert fixtures["ai-consulting"].expected_status == "READY_FOR_ACCEPTANCE"
    assert fixtures["haloehs"].expected_status == "UNSUPPORTED_TENANT"
    assert all(fixture.owner_email.endswith(".test") for fixture in fixtures.values())


def test_dry_run_executes_launch_tenants_and_rejects_halo() -> None:
    service = InMemoryOnboardingService(FakeProviderHub())
    fixtures = phase1_dry_run_fixtures()
    assert service.run("ara-global").status == StageStatus.SUCCEEDED
    assert service.run("ai-consulting").status == StageStatus.SUCCEEDED
    with pytest.raises(ValueError, match="unsupported phase1 tenant"):
        service.run(fixtures["haloehs"].tenant_key)


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
