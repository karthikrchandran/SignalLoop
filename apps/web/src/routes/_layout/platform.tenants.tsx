import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/platform/tenants")({
  component: PlatformTenants,
})

function PlatformTenants() {
  return (
    <TenantAdminWorkspacePage
      title="Tenants"
      description="Manage tenant lifecycle and provisioning. Selecting a tenant never grants access to its business data."
      sections={["Tenant lifecycle", "Entitlements", "Administrators", "Tenant audit"]}
    />
  )
}
