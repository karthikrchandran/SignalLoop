import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/admin/messaging")({ component: TenantMessaging })

function TenantMessaging() {
  return (
    <TenantAdminWorkspacePage
      title="Messaging"
      description="Set tenant defaults for channels, consent, and provider configuration."
      sections={["Channel defaults", "Consent and suppression", "Provider policy", "Messaging audit"]}
    />
  )
}
