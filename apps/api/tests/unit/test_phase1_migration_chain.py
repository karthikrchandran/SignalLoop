from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load(name: str, filename: str):
    path = Path(__file__).parents[2] / "app" / "alembic" / "versions" / filename
    spec = spec_from_file_location(name, path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_onboarding_follows_branding_in_the_phase_one_chain() -> None:
    onboarding = _load(
        "phase1_onboarding", "p1_onboard_20260810_add_onboarding_runs.py"
    )
    assert onboarding.down_revision == "p1_branding_20260810"


def test_phase_one_history_keeps_the_prior_sales_agent_revision_reachable() -> None:
    sales_agent = _load(
        "sales_agent_history", "sales_agent_20260809_add_supervised_loop.py"
    )
    merge = _load("phase1_merge", "p1_merge_20260810_restore_sales_agent_head.py")

    assert sales_agent.revision == "sales_agent_20260809"
    assert sales_agent.down_revision == "psid_20260726"
    assert set(merge.down_revision) == {"sales_agent_20260809", "p1_onboard_20260810"}


def test_onboarding_hardening_merges_current_heads_before_altering_run_scope() -> None:
    hardening = _load("onboarding_hardening", "onboarding_hardening_20260812.py")
    assert set(hardening.down_revision) == {
        "phase1_merge_20260812",
        "p1_ecrm_install_q_20260812",
    }


def test_commercial_agent_registry_extends_the_current_phase_one_head() -> None:
    registry = _load(
        "commercial_agent_registry", "p1_commercial_agent_registry_20260816.py"
    )
    assert registry.revision == "p1_commercial_agent_registry_20260816"
    assert registry.down_revision == "p1_tenant_workspace_binding_20260812"


def test_commercial_agent_catalog_seed_extends_the_registry_schema() -> None:
    catalog = _load(
        "commercial_agent_catalog", "p1_commercial_agent_catalog_20260816.py"
    )
    assert catalog.revision == "p1_commercial_agent_catalog_20260816"
    assert catalog.down_revision == "p1_commercial_agent_registry_20260816"
