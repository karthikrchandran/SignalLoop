import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/platform/support-access")({ component: SupportAccess })

function SupportAccess() {
  return (
    <TenantAdminWorkspacePage
      title="Support access"
      description="Approve, time-bound, revoke, and audit tenant support grants."
      sections={["Pending grants", "Active grants", "Expired grants", "Support-access audit"]}
    />
  )
}
