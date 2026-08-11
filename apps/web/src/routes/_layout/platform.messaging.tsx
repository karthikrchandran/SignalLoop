import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/platform/messaging")({ component: PlatformMessaging })

function PlatformMessaging() {
  return (
    <TenantAdminWorkspacePage
      title="Messaging defaults"
      description="Set safe platform defaults for tenant messaging operations."
      sections={["Channel defaults", "Consent defaults", "Suppression defaults", "Template policy"]}
    />
  )
}
