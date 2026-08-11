import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/admin/audit")({ component: TenantAudit })

function TenantAudit() {
  return (
    <TenantAdminWorkspacePage
      title="Tenant audit"
      description="Review tenant-scoped administrative changes and support access."
      sections={["Membership changes", "Entitlement changes", "Branding changes", "Support access"]}
    />
  )
}
