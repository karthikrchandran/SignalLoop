from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5


@dataclass(frozen=True)
class TenantSecurityFixture:
    workspace_id: str
    contact_email: str


def tenant_fixture(test_namespace: str, tenant_key: str) -> TenantSecurityFixture:
    return TenantSecurityFixture(
        workspace_id=f"test-{uuid5(NAMESPACE_URL, f'signalloop:{test_namespace}:{tenant_key}').hex}",
        contact_email="enterprise-contact@example.com",
    )


def tenant_pair(test_namespace: str) -> tuple[TenantSecurityFixture, TenantSecurityFixture]:
    return (
        tenant_fixture(test_namespace, "alpha"),
        tenant_fixture(test_namespace, "beta"),
    )
