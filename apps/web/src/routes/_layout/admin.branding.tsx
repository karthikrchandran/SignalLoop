import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/admin/branding")({ component: TenantBranding })

function TenantBranding() {
  return (
    <TenantAdminWorkspacePage
      title="Branding"
      description="Prepare, validate, publish, and roll back tenant branding versions."
      sections={["Draft branding", "Validate assets", "Published version", "Rollback history"]}
    />
  )
}
