"""Synthetic only fixtures used by the onboarding acceptance harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnboardingDryRunFixture:
    tenant_key: str
    owner_email: str
    expected_status: str
    uses_synthetic_records: bool = True


def phase1_dry_run_fixtures() -> dict[str, OnboardingDryRunFixture]:
    """Launch fixtures deliberately contain no customer record or provider data."""
    return {
        "ara-global": OnboardingDryRunFixture(
            tenant_key="ara-global",
            owner_email="owner@ara-global.test",
            expected_status="READY_FOR_ACCEPTANCE",
        ),
        "ai-consulting": OnboardingDryRunFixture(
            tenant_key="ai-consulting",
            owner_email="owner@ai-consulting.test",
            expected_status="READY_FOR_ACCEPTANCE",
        ),
        "haloehs": OnboardingDryRunFixture(
            tenant_key="haloehs",
            owner_email="owner@haloehs.test",
            expected_status="UNSUPPORTED_TENANT",
        ),
    }
