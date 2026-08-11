import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/platform/products")({ component: PlatformProducts })

function PlatformProducts() {
  return (
    <TenantAdminWorkspacePage
      title="Products"
      description="Manage suite product availability and default entitlement policy."
      sections={["CommitArc", "RevenueOS", "SignalLoop", "Entitlement policy"]}
    />
  )
}
