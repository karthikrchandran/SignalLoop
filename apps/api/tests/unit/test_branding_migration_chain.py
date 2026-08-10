from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_branding_migration_follows_installation_head() -> None:
    path = Path(__file__).parents[2] / "app" / "alembic" / "versions" / "p1_branding_20260810_add_tenant_branding.py"
    spec = spec_from_file_location("branding_migration", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "p1_branding_20260810"
    assert module.down_revision == "p1_install_20260809"
