import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/admin/security")({ component: TenantSecurity })

function TenantSecurity() {
  return (
    <TenantAdminWorkspacePage
      title="Security"
      description="Review tenant identity, access, and time-bounded support controls."
      sections={["Role bundles", "Identity policy", "Support grants", "Security audit"]}
    />
  )
}
