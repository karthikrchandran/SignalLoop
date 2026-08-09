from dataclasses import dataclass


@dataclass(frozen=True)
class TenantSecurityFixture:
    workspace_id: str
    contact_email: str


def tenant_fixture(tenant_key: str) -> TenantSecurityFixture:
    return TenantSecurityFixture(
        workspace_id=f"test-workspace-{tenant_key}",
        contact_email="enterprise-contact@example.com",
    )


def tenant_pair() -> tuple[TenantSecurityFixture, TenantSecurityFixture]:
    return tenant_fixture("alpha"), tenant_fixture("beta")
