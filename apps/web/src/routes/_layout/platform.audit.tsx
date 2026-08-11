import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/platform/audit")({ component: PlatformAudit })

function PlatformAudit() {
  return (
    <TenantAdminWorkspacePage
      title="Platform audit"
      description="Review control-plane administration, tenant lifecycle, and support-access events."
      sections={["Tenant lifecycle", "Entitlements", "Identity changes", "Support access"]}
    />
  )
}
