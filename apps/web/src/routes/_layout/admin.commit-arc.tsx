import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"
import { requireProductAdmin } from "@/features/admin/requireProductAdmin"

export const Route = createFileRoute("/_layout/admin/commit-arc")({
  beforeLoad: () => requireProductAdmin("commitarc.admin.manage"),
  component: CommitArcAdmin,
})

function CommitArcAdmin() {
  return (
    <TenantAdminWorkspacePage
      title="CommitArc administration"
      description="Configure the tenant's CommitArc commercial operating controls."
      sections={["Business settings", "Pipeline and catalog", "Proposals and numbering", "Delivery and production", "Finance and incentives", "CommitArc audit"]}
    />
  )
}
