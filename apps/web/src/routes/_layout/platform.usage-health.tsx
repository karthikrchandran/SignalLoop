import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/platform/usage-health")({ component: UsageHealth })

function UsageHealth() {
  return (
    <TenantAdminWorkspacePage
      title="Usage and health"
      description="Review operational health and usage indicators without exposing tenant business data."
      sections={["Service health", "Provider health", "Usage limits", "Operational incidents"]}
    />
  )
}
