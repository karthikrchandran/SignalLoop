import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/admin/members")({
  component: TenantMembers,
})

function TenantMembers() {
  return (
    <TenantAdminWorkspacePage
      title="People and roles"
      description="Manage memberships and role bundles for this tenant only."
      sections={["Tenant owners", "Product administrators", "Employees and managers", "Invitation history"]}
    />
  )
}
