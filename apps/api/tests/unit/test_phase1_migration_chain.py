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
