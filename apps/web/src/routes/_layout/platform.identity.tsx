import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/platform/identity")({ component: PlatformIdentity })

function PlatformIdentity() {
  return (
    <TenantAdminWorkspacePage
      title="Identity"
      description="Set platform identity defaults and review authentication policy."
      sections={["OIDC configuration", "Session policy", "Invitation policy", "Identity audit"]}
    />
  )
}
