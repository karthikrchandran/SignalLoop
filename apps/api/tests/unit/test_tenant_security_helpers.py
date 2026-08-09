from tests.utils.tenant_security import tenant_pair


def test_tenant_pair_has_distinct_workspace_ids() -> None:
    alpha, beta = tenant_pair()

    assert alpha.workspace_id != beta.workspace_id
    assert alpha.contact_email == beta.contact_email
