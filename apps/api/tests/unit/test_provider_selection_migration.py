from importlib import import_module

from app.domain_models import NotificationProvider, ProviderCapability


def test_provider_selection_migration_enum_values_match_domain_enums() -> None:
    migration = import_module(
        "app.alembic.versions.m8b9c0d1e2f3_add_workspace_provider_selection_and_capability_enums"
    )

    assert set(migration.ALL_PROVIDER_VALUES) == {
        provider.value for provider in NotificationProvider
    }
    assert set(migration.CAPABILITY_VALUES) == {
        capability.value for capability in ProviderCapability
    }
    assert len(migration.ALL_PROVIDER_VALUES) == len(set(migration.ALL_PROVIDER_VALUES))
