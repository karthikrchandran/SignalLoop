import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/admin/products")({ component: TenantProducts })

function TenantProducts() {
  return (
    <TenantAdminWorkspacePage
      title="Products"
      description="Manage which suite products are enabled for this tenant."
      sections={["CommitArc entitlement", "RevenueOS entitlement", "SignalLoop entitlement", "Product administrator roles"]}
    />
  )
}
