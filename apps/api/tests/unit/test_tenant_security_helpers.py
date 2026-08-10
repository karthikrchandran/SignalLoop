from tests.utils.tenant_security import tenant_pair


def test_tenant_pair_has_distinct_workspace_ids() -> None:
    alpha, beta = tenant_pair("workspace_membership")

    assert alpha.workspace_id != beta.workspace_id
    assert alpha.contact_email == beta.contact_email


def test_tenant_pair_is_deterministic_per_namespace() -> None:
    first = tenant_pair("workspace_membership")
    repeated = tenant_pair("workspace_membership")
    other_scenario = tenant_pair("contact_visibility")

    assert repeated == first
    assert {fixture.workspace_id for fixture in first}.isdisjoint(
        fixture.workspace_id for fixture in other_scenario
    )
