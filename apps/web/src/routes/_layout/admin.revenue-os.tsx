import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"
import { requireProductAdmin } from "@/features/admin/requireProductAdmin"

export const Route = createFileRoute("/_layout/admin/revenue-os")({
  beforeLoad: () => requireProductAdmin("revenueos.admin.manage"),
  component: RevenueOsAdmin,
})

function RevenueOsAdmin() {
  return (
    <TenantAdminWorkspacePage
      title="RevenueOS administration"
      description="Control tenant-specific RevenueOS policy, autonomy, and operational limits."
      sections={["AI Control Center", "Knowledge Releases", "Policies and Autonomy", "Intervention Queue", "Budgets and Limits", "Outcomes", "RevenueOS Audit"]}
    />
  )
}
