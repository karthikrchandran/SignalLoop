from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceRecorder
from .manifest import load_phase1_manifests
from .models import OnboardingRun, OnboardingStage, StageStatus
from .providers import FakeProviderHub


@dataclass
class InMemoryOnboardingService:
    providers: FakeProviderHub

    def __post_init__(self) -> None:
        self.runs: dict[str, OnboardingRun] = {}
        self._by_key: dict[str, OnboardingRun] = {}
        self._tenants: set[str] = set()
        self._entitlements: dict[str, set[str]] = {}
        self.evidence = EvidenceRecorder()

    def run(self, tenant_key: str, *, fail_at: OnboardingStage | None = None) -> OnboardingRun:
        manifest = load_phase1_manifests().get(tenant_key)
        if manifest is None:
            raise ValueError(f"unsupported phase1 tenant: {tenant_key}")
        run = self._by_key.get(f"onboarding:{tenant_key}:phase1")
        if run is None:
            run = OnboardingRun(tenant_key)
            self.runs[run.run_id] = run
            self._by_key[run.idempotency_key or ""] = run
        self._execute(run, fail_at=fail_at)
        return run

    def retry(self, run_id: str) -> OnboardingRun:
        run = self.runs[run_id]
        self._execute(run)
        return run

    def _execute(self, run: OnboardingRun, *, fail_at: OnboardingStage | None = None) -> None:
        run.attempts += 1
        run.status = StageStatus.RUNNING
        for stage, result in run.stages.items():
            if result.status is StageStatus.SUCCEEDED:
                continue
            result.status = StageStatus.RUNNING
            result.attempts += 1
            if stage is OnboardingStage.TENANT_DRAFTED:
                outcome = self.providers.provision_tenant(run.tenant_key)
                self._tenants.add(run.tenant_key)
            elif stage is OnboardingStage.PRODUCTS_ASSIGNED:
                products = set(load_phase1_manifests()[run.tenant_key].products)
                self._entitlements.setdefault(run.tenant_key, set()).update(products)
                outcome = "UPDATED"
            elif stage is OnboardingStage.NATIVE_INTEGRATION_VERIFIED:
                if fail_at is stage:
                    result.status = StageStatus.FAILED
                    result.result_code = "NATIVE_CANARY_FAILED"
                    run.status = StageStatus.FAILED
                    return
                outcome = "UNCHANGED"
            else:
                outcome = "UNCHANGED"
            result.status = StageStatus.SUCCEEDED
            result.result_code = outcome
            evidence = self.evidence.record(run.run_id, stage.value, outcome, {"tenant": run.tenant_key})
            result.evidence_refs.append(evidence.digest)
        run.status = StageStatus.SUCCEEDED

    def count_tenants(self, tenant_key: str) -> int:
        return int(tenant_key in self._tenants)

    def count_entitlements(self, tenant_key: str) -> int:
        return len(self._entitlements.get(tenant_key, set()))
